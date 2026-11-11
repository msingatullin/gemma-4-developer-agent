#!/usr/bin/env python3
"""Deterministic, fail-closed salvage of malformed model-authored unified diffs.

Rebases change clusters against a *pinned base source*. Never loads gold
patches, expected test output, or runtime traces. Each removed line sequence
must be unique, and insertion-only clusters need unique exact context.
Candidate source and originally permitted target path are preserved.
If a prose-only documentation hunk cannot be placed exactly, it is dropped
and reported; this is post-hoc parsing repair, not 'raw model success'.
"""
import ast
import difflib
import hashlib
import re

def salvage(source: str, model_diff: str, target_path: str):
    from evaluate_real_repo_patches import validate_candidate_diff_paths
    ok, reason=validate_candidate_diff_paths(model_diff,target_path)
    if not ok: return None,{'reason':'unsafe_model_diff:'+reason}
    hunks=re.split(r'(?=^@@ -\d+)',model_diff,flags=re.M)[1:]
    if not hunks: return None,{'reason':'no_hunks'}
    edits=[];skipped=[]
    for hi,hunk in enumerate(hunks):
        lines=hunk.splitlines()[1:]
        # Safety: no blank or unsupported marker payload.
        if any(not s or s[0] not in ('+','-',' ','\\') for s in lines):
            return None,{'reason':'unknown_hunk_line','hunk':hi}
        clusters=[];run=[]
        for idx,line in enumerate(lines):
            if line[0] in ('+','-'):
                run.append((idx,line))
            elif run:
                clusters.append(run);run=[]
        if run:clusters.append(run)
        for cluster in clusters:
            start,end=cluster[0][0],cluster[-1][0]
            adds=[s[1:] for _,s in cluster if s.startswith('+')]
            deletes=[s[1:] for _,s in cluster if s.startswith('-')]
            if deletes:
                old='\n'.join(deletes)+'\n'
                new='\n'.join(adds)+'\n'
                if source.count(old)!=1:
                    return None,{'reason':'nonunique_deleted_span','hunk':hi,'count':source.count(old)}
                edits.append((old,new,hi))
                continue
            if not adds:continue
            # Insertions with existing docstring lines may be redundant.
            if all(s.lstrip().startswith(':param ') for s in adds):
                skipped.append({'hunk':hi,'reason':'optional_documentation_only','lines':len(adds)})
                continue
            before=next((s[1:] for s in reversed(lines[:start]) if s.startswith(' ')),None)
            after=next((s[1:] for s in lines[end+1:] if s.startswith(' ')),None)
            if before is None or after is None:
                return None,{'reason':'no_unique_context_for_insertion','hunk':hi}
            key=before+'\n'+after+'\n'
            if source.count(key)!=1:
                return None,{'reason':'nonunique_insertion_context','hunk':hi,'count':source.count(key)}
            new=before+'\n'+'\n'.join(adds)+'\n'+after+'\n'
            edits.append((key,new,hi))
    if not edits:return None,{'reason':'no_code_edits'}
    updated=source
    for old,new,hi in edits:
        if updated.count(old)!=1:
            return None,{'reason':'ambiguous_after_previous_edit','hunk':hi}
        updated=updated.replace(old,new,1)
    try:ast.parse(updated)
    except SyntaxError as e:return None,{'reason':'syntax_after_edit','msg':str(e)}
    diff=''.join(difflib.unified_diff(source.splitlines(keepends=True),
                  updated.splitlines(keepends=True),fromfile='a/'+target_path,
                  tofile='b/'+target_path))
    if not diff:return None,{'reason':'no_source_change'}
    return diff,{'reason':'unique_source_anchored_hunk_salvage',
                 'replacements':len(edits),'doc_hunks_omitted':skipped,
                 'candidate_sha256':hashlib.sha256(diff.encode()).hexdigest()}
