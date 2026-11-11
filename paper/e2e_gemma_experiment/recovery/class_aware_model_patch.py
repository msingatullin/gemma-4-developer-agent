#!/usr/bin/env python3
"""Generic class-aware repair for LLM generated Python methods.

Input is first-pass model text and pinned base module; no gold patches or test
answers are read. May recover formatting errors and disambiguate method owner.
Transforms to an allowlisted single-module unified diff for strict evaluator.
"""
import ast
import difflib
import hashlib
import re
import textwrap

def locate_code(output):
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from evaluate_real_repo_patches import extract_candidate_code
    return extract_candidate_code(output)

def normalize_bad_sibling_indentation(code):
    try:
        ast.parse(code)
        return code, False
    except (SyntaxError, IndentationError) as exc:
        if "unindent does not match any outer indentation level" not in str(exc):
            return code, False
    lines=code.splitlines(keepends=True)
    tops=[i for i,x in enumerate(lines) if re.match(r'^(?:async )?def\s+[A-Za-z_]\w*\s*\(',x)]
    incorrectly_indented=[i for i,x in enumerate(lines) if re.match(r'^ {4}(?:async )?def\s+[A-Za-z_]\w*\s*\(',x)]
    if len(tops)!=1 or len(incorrectly_indented)!=1 or incorrectly_indented[0]<=tops[0]:
        return code,False
    at=incorrectly_indented[0]
    new=''.join(lines[:at])+''.join(x[4:] if x.startswith('    ') else x for x in lines[at:])
    try:
        ast.parse(new)
    except SyntaxError:
        return code,False
    return new, True

def transform_output(model_output,base_source,target_relative_path):
    """Return (response_for_original_strict_evaluator, metadata).
    
    Conservatively returns input unchanged for unsupported candidates.
    """
    code, kind=locate_code(model_output)
    meta={'transformed':False,'indent_recovered':False,'reason':'unchanged'}
    if kind!='python':
        meta['reason']='not_python'
        return model_output,meta
    code,recovered=normalize_bad_sibling_indentation(code)
    try:
        parsed=ast.parse(code)
        base=ast.parse(base_source)
    except SyntaxError:
        meta['reason']='unrepairable_python'
        return model_output,meta
    methods=[x for x in parsed.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))]
    if not methods:
        meta['reason']='no_top_level_methods'
        return model_output,meta
    classes=[x for x in base.body if isinstance(x,ast.ClassDef)]
    # Only transform if all candidate functions are methods in the SAME class.
    compatible=[]
    for cls in classes:
        byname={x.name:x for x in cls.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}
        if all(m.name in byname for m in methods):
            compatible.append(cls)
    if not compatible:
        meta['reason']='not_class_methods'
        return model_output,meta
    owner_classes=[]
    # Only concrete model output BEFORE PROPOSED_CODE can disambiguate.
    header=model_output.split('PROPOSED_CODE:',1)[0]
    for cls in compatible:
        if any(re.search(r'\b'+re.escape(cls.name)+r'\.'+re.escape(m.name)+r'\b',header)
               for m in methods):
            owner_classes.append(cls)
    if len(owner_classes)!=1:
        meta['reason']='class_ambiguous'
        return model_output,meta
    cls=owner_classes[0]
    byname={x.name:x for x in cls.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}
    base_lines=base_source.splitlines(keepends=True)
    edits=[]
    for n in methods:
        original=byname[n.name]
        text=ast.get_source_segment(code,n)
        if not text:
            meta['reason']='source_unavailable'
            return model_output,meta
        # Conservative: do not drop decorators by accident.
        if original.decorator_list or n.decorator_list:
            meta['reason']='decorated_method_unsupported'
            return model_output,meta
        new=textwrap.indent(text,' '*original.col_offset)+'\n'
        edits.append((original.lineno,original.end_lineno,new))
    for start,end,new in sorted(edits,reverse=True):
        base_lines[start-1:end]=[new]
    new_source=''.join(base_lines)
    try:
        ast.parse(new_source)
    except SyntaxError:
        meta['reason']='post_edit_invalid'
        return model_output,meta
    if new_source==base_source:
        meta['reason']='no_change'
        return model_output,meta
    diff=''.join(difflib.unified_diff(
        base_source.splitlines(keepends=True),
        new_source.splitlines(keepends=True),
        fromfile='a/'+target_relative_path,
        tofile='b/'+target_relative_path
    ))
    assert diff.startswith('--- a/'+target_relative_path) and '\n+++ b/'+target_relative_path in diff
    response='PROPOSED_CODE:\n'+chr(96)*3+'diff\n'+diff+chr(96)*3
    return response,{
        'transformed':True,
        'indent_recovered':recovered,
        'reason':'class_aware_ast_multi_method_splice',
        'class':cls.name,
        'methods':[x.name for x in methods],
        'candidate_sha256':hashlib.sha256(response.encode()).hexdigest(),
    }
