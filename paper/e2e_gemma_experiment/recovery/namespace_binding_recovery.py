#!/usr/bin/env python3
"""Post-hoc static missing-binding recovery for model-supplied method patches.

The adapter reads ONLY the model response, the frozen base source, and the
corresponding frozen repository's own exception module. It does not inspect
gold patches or test assertions. It is not a model inference algorithm.
"""
import ast
import hashlib
import re
import sys
import textwrap
import subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def recover_import_bindings(model_response, base_source, rel_path, base_commit, repo_bare):
    from evaluate_real_repo_patches import extract_candidate_code
    candidate,kind=extract_candidate_code(model_response)
    no={'transformed':False,'reason':'no_safe_repair'}
    if kind!='python':
        return model_response,{**no,'reason':'not_python'}
    try:
        cand_tree=ast.parse(candidate)
        base_tree=ast.parse(base_source)
    except SyntaxError:
        return model_response,{**no,'reason':'invalid_candidate'}
    meth=[n for n in cand_tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    if len(meth)!=1 or len(cand_tree.body)!=1:
        return model_response,{**no,'reason':'not_single_method'}
    cls=[cl for cl in base_tree.body if isinstance(cl,ast.ClassDef) and any(isinstance(m,ast.FunctionDef) and m.name==meth[0].name for m in cl.body)]
    if len(cls)!=1:
        return model_response,{**no,'reason':'ambiguous_class_owner'}
    target=next(x for x in cls[0].body if isinstance(x,ast.FunctionDef) and x.name==meth[0].name)
    if target.decorator_list or meth[0].decorator_list:
        return model_response,{**no,'reason':'decorated_method'}
    snippet=ast.get_source_segment(candidate,meth[0])
    if not snippet:
        return model_response,{**no,'reason':'missing_source'}
    lines=base_source.splitlines(keepends=True)
    lines[target.lineno-1:target.end_lineno]=[textwrap.indent(snippet,' '*target.col_offset)+'\n']
    fixed=''.join(lines)
    ast.parse(fixed)

    module_imports={alias.asname or alias.name.split('.')[0] for node in base_tree.body if isinstance(node,ast.Import) for alias in node.names}
    unbound_stdlib=sorted({node.value.id for node in ast.walk(meth[0])
                           if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name)
                           and node.value.id in sys.stdlib_module_names
                           and node.value.id not in module_imports})
    # Fail closed on multiple speculative dependencies.
    if len(unbound_stdlib)!=1:
        return model_response,{**no,'reason':'stdlib_resolution_ambiguous','unbound_count':len(unbound_stdlib)}

    symbol=unbound_stdlib[0]
    if symbol in {'builtins','__future__'}:
        return model_response,{**no,'reason':'stdlib_name_restricted'}
    lines=fixed.splitlines(keepends=True)
    t=ast.parse(fixed)
    imports=[node for node in t.body if isinstance(node,(ast.Import,ast.ImportFrom)) and not (isinstance(node,ast.ImportFrom) and node.module=='__future__')]
    if not imports:
        return model_response,{**no,'reason':'no_import_anchor'}
    lines.insert(imports[0].lineno-1,'import '+symbol+'\n')
    fixed=''.join(lines)
    added=['import '+symbol]

    # If candidate throws a same-named exception also defined in this
    # package's own exceptions.py, bind to the package exception class.
    candidate_raise_names={n.exc.func.id if isinstance(n.exc,ast.Call) and isinstance(n.exc.func,ast.Name)
                           else n.exc.id for n in ast.walk(meth[0]) if isinstance(n,ast.Raise)
                           and n.exc is not None
                           and (isinstance(n.exc,ast.Name) or
                                (isinstance(n.exc,ast.Call) and isinstance(n.exc.func,ast.Name)))}
    base_exceptions_imports=[n for n in base_tree.body if isinstance(n,ast.ImportFrom) and n.module=='exceptions' and n.level==1]
    sibling=(Path(rel_path).parent/'exceptions.py').as_posix()
    if candidate_raise_names and len(base_exceptions_imports)==1 and '..' not in Path(rel_path).parts:
        try:
            exc_source=subprocess.check_output(
                ['git',f'--git-dir={repo_bare}','show',f'{base_commit}:{sibling}'],
                text=True,stderr=subprocess.DEVNULL,timeout=12)
            exc_tree=ast.parse(exc_source)
            exported={n.name for n in exc_tree.body if isinstance(n,ast.ClassDef)}
            already={alias.asname or alias.name for alias in base_exceptions_imports[0].names}
            bind=sorted((candidate_raise_names & exported) - already)
            if len(bind)>1:
                return model_response,{**no,'reason':'package_exception_ambiguous'}
            if bind:
                line='from .exceptions import '+bind[0]
                t=ast.parse(fixed)
                here=next(n for n in t.body if isinstance(n,ast.ImportFrom) and n.level==1 and n.module=='exceptions')
                lines=fixed.splitlines(keepends=True)
                lines.insert(here.end_lineno,line+'\n')
                fixed=''.join(lines);added.append(line)
        except (OSError,subprocess.SubprocessError,SyntaxError):
            return model_response,{**no,'reason':'package_exception_unavailable'}
    ast.parse(fixed)
    if fixed==base_source:
        return model_response,{**no,'reason':'no_change'}
    answer='PROPOSED_CODE:\n'+chr(96)*3+'python\n'+fixed+'\n'+chr(96)*3
    return answer,{
        'transformed':True,
        'reason':'model_method_plus_static_namespace_binding',
        'class':cls[0].name,
        'method':meth[0].name,
        'added_imports':added,
        'candidate_sha256':hashlib.sha256(answer.encode()).hexdigest()
    }

