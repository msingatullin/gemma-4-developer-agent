import re
from collections import Counter

def filter_pytest_log(raw_log: str) -> str:
    """
    Multi-format, multi-failure traceback compressor:
    1. Drops true platform session banners (anchored to line start).
    2. Separates and preserves all distinct failure blocks.
    3. In each failure block, collapses bulky captured stdout/stderr buffers.
    4. Preserves failing code sites, line pointers, and ALL diagnostic assertion lines across:
       - Standard Pytest formats (--tb=auto, --tb=long, --tb=short): lines starting with 'E ' or 'E\t'.
       - Native tracebacks (--tb=native and standalone Python): last failing frame and complete exception message.
    5. Preserves all FAILED test summary lines.
    6. Untruncated safe fallback: preserves full log without arbitrary line capping if unrecognized or if compression loses evidence.
    """
    # Conservative fallback: never reorder exception chains or exception groups.
    if any(marker in raw_log for marker in (
        'During handling of the above exception',
        'The above exception was the direct cause',
        'ExceptionGroup',
    )):
        return raw_log

    # Native tracebacks can contain multi-line details that are not
    # safely parseable into E-lines; preserve them in full until verified.
    if 'Traceback (most recent call last):' in raw_log:
        return raw_log

    lines = raw_log.splitlines()
    summary_lines = [l for l in lines if re.match(r'^(FAILED|ERROR)\s+', l.strip())]
    
    failure_blocks = []
    current_block = []
    in_failures_zone = False
    in_captured_output = False
    
    for line in lines:
        stripped = line.strip()
        
        # Detect entering failures zone
        if re.search(r'^=+\s*(FAILURES|ERRORS)\s*=+', stripped):
            in_failures_zone = True
            continue
            
        if not in_failures_zone:
            if re.match(r'^(platform|rootdir:|collected\s+\d+)', stripped):
                continue
            if stripped.startswith('plugins:') and not any(k in stripped.lower() for k in ('error', 'fail', 'exception', 'invalid')):
                continue
            continue
            
        # End failure recording upon reaching summary
        if re.search(r'^=+\s*short test summary info\s*=+', stripped):
            if current_block:
                failure_blocks.append(current_block)
                current_block = []
            break
            
        # Detect start of a new individual test failure
        if re.match(r'^_{3,}\s*.*?\s*_{3,}$', stripped):
            if current_block:
                failure_blocks.append(current_block)
                current_block = []
            current_block.append(line)
            in_captured_output = False
            continue
            
        # Detect captured stdout/stderr inside a test failure
        if re.search(r'^-+\s*Captured (stdout|stderr)\s*', stripped):
            in_captured_output = True
            current_block.append('    --- [Captured output collapsed] ---')
            continue
            
        if in_captured_output:
            if re.match(r'^(=|_|-){3,}', stripped) or re.match(r'^(FAILED|ERROR)\s+', stripped):
                in_captured_output = False
            else:
                continue
                
        # Skip pure decorative separator lines
        if not re.match(r'^[=_-]{10,}$', stripped):
            current_block.append(line)
            
    if current_block:
        failure_blocks.append(current_block)
        
    # Fallback if no pytest failure blocks were detected
    if not failure_blocks:
        filtered = [l for l in lines if not re.match(r'^(platform|rootdir:|collected\s+\d+)', l.strip())]
        return '\n'.join(filtered)

    compressed_sections = []
    for block in failure_blocks:
        header = block[:1]
        body_lines = []
        has_collapsed_stdout = False
        
        # Check if block uses standard pytest E-lines or native traceback
        has_e_lines = any(l.strip().startswith('E ') or l.strip().startswith('E\t') for l in block[1:])
        
        if has_e_lines:
            for l in block[1:]:
                s = l.strip()
                if '--- [Captured output collapsed] ---' in l:
                    has_collapsed_stdout = True
                    continue
                if s.startswith('>') or s.startswith('E ') or s.startswith('E\t') or re.search(r':\s*in\s+\w+', l) or re.search(r'\.py:\d+:\s+\w+Error', s):
                    body_lines.append(l)
                elif not body_lines and len(header) < 3 and s:
                    header.append(l)
        else:
            in_exc_msg = False
            last_file_frame = []
            for l in block[1:]:
                s = l.strip()
                if '--- [Captured output collapsed] ---' in l:
                    has_collapsed_stdout = True
                    continue
                if re.match(r'^\s*File\s+\".*?\",\s+line\s+\d+', l):
                    last_file_frame = [l]
                    in_exc_msg = False
                elif last_file_frame and not in_exc_msg and re.match(r'^\s*\w*(?:Error|Exception):', s):
                    body_lines.extend(last_file_frame)
                    last_file_frame = []
                    body_lines.append(l)
                    in_exc_msg = True
                elif in_exc_msg:
                    body_lines.append(l)
                elif last_file_frame:
                    last_file_frame.append(l)
            if not body_lines and last_file_frame:
                body_lines.extend(last_file_frame)
            if not body_lines:
                body_lines = [l for l in block[1:] if '--- [Captured output collapsed] ---' not in l]
                
        comp = header.copy()
        if len(block) > len(header) + len(body_lines) + 4:
            comp.append('    ... [intermediate frames omitted] ...')
        comp.extend(body_lines)
        if has_collapsed_stdout:
            comp.append('    --- [Captured output collapsed] ---')
            
        compressed_sections.append('\n'.join(comp))
        
    output_parts = ['\n'.join(compressed_sections)]
    if summary_lines:
        output_parts.append('\n'.join(summary_lines))
        
    proposed = '\n'.join(output_parts)

    # Fail-open diagnostic integrity guard
    def diagnostic_lines(value):
        return Counter(
            line.strip() for line in value.splitlines()
            if (line.lstrip().startswith(('E ', 'E\t', '> ', 'FAILED ', 'ERROR '))
                or re.match(r'^[\w.]+(?:Error|Exception|Warning|Exit|Interrupt):', line.strip()))
        )
    original_evidence = diagnostic_lines(raw_log)
    compressed_evidence = diagnostic_lines(proposed)

    failure_header = re.compile(r'^_{3,}\s*.*?\s*_{3,}$')
    original_headers = Counter(
        l.strip() for l in raw_log.splitlines()
        if failure_header.match(l.strip())
    )
    compressed_headers = Counter(
        l.strip() for l in proposed.splitlines()
        if failure_header.match(l.strip())
    )
    if any(compressed_headers[line] < count for line, count in original_headers.items()):
        return raw_log
    if any(compressed_evidence[line] < count for line, count in original_evidence.items()):
        return raw_log

    return proposed


def filter_pytest_log_v2(raw_log: str) -> str:
    """
    Assertion-aware pytest log compressor (v2 for B2_assertion_aware):
    1. Preserves pytest.raises(..., match=...) and pytest.warns contexts (including regex match strings).
    2. Preserves assertion statements (assert ...), caret underlines (^^^^^), and test comments.
    3. Preserves local context lines immediately preceding failing test sites (>).
    4. Handles multi-line pytest diff blocks including bare 'E' separator lines.
    5. Preserves distinct failure blocks, file/line anchors, and summary status lines.
    6. Collapses captured stdout/stderr noisy logging blocks.
    7. Safe fallback: fail-open integrity guard comparing diagnostic lines counter against raw log.
    """
    # Conservative fallback: never reorder exception chains or exception groups.
    if any(marker in raw_log for marker in (
        'During handling of the above exception',
        'The above exception was the direct cause',
        'ExceptionGroup',
    )):
        return raw_log

    # Native tracebacks can contain multi-line details that are not
    # safely parseable into E-lines; preserve them in full until verified.
    if 'Traceback (most recent call last):' in raw_log:
        return raw_log

    lines = raw_log.splitlines()
    summary_lines = [l for l in lines if re.match(r'^(FAILED|ERROR)\s+', l.strip())]

    failure_blocks = []
    current_block = []
    in_failures_zone = False
    in_captured_output = False

    for line in lines:
        stripped = line.strip()

        # Detect entering failures zone
        if re.search(r'^=+\s*(FAILURES|ERRORS)\s*=+', stripped):
            in_failures_zone = True
            continue

        if not in_failures_zone:
            if re.match(r'^(platform|rootdir:|collected\s+\d+)', stripped):
                continue
            if stripped.startswith('plugins:') and not any(k in stripped.lower() for k in ('error', 'fail', 'exception', 'invalid')):
                continue
            continue

        # End failure recording upon reaching summary
        if re.search(r'^=+\s*short test summary info\s*=+', stripped):
            if current_block:
                failure_blocks.append(current_block)
                current_block = []
            break

        # Detect start of a new individual test failure
        if re.match(r'^_{3,}\s*.*?\s*_{3,}$', stripped):
            if current_block:
                failure_blocks.append(current_block)
                current_block = []
            current_block.append(line)
            in_captured_output = False
            continue

        # Detect captured stdout/stderr inside a test failure
        if re.search(r'^-+\s*Captured (stdout|stderr)\s*', stripped):
            in_captured_output = True
            current_block.append('    --- [Captured output collapsed] ---')
            continue

        if in_captured_output:
            if re.match(r'^(=|_|-){3,}', stripped) or re.match(r'^(FAILED|ERROR)\s+', stripped):
                in_captured_output = False
            else:
                continue

        # Skip pure decorative separator lines
        if not re.match(r'^[=_-]{10,}$', stripped):
            current_block.append(line)

    if current_block:
        failure_blocks.append(current_block)

    # Fallback if no pytest failure blocks were detected
    if not failure_blocks:
        filtered = [l for l in lines if not re.match(r'^(platform|rootdir:|collected\s+\d+)', l.strip())]
        return '\n'.join(filtered)

    compressed_sections = []
    for block in failure_blocks:
        header = block[:1]
        has_collapsed_stdout = False

        has_e_lines = any(l.lstrip().startswith(('E ', 'E\t')) or l.strip() == 'E' for l in block[1:])

        if has_e_lines:
            block_tail = block[1:]
            keep_indices = set()

            for i, l in enumerate(block_tail):
                s = l.strip()
                ls = l.lstrip()
                if '--- [Captured output collapsed] ---' in l:
                    has_collapsed_stdout = True
                    continue
                # 1. Error messages, assertion diffs, and exception lines
                if ls.startswith(('E ', 'E\t')) or s == 'E' or re.search(r'\.py:\d+:\s+\w+Error', s):
                    keep_indices.add(i)
                # 2. Failing code lines (marked with >) and local context
                elif s.startswith('>'):
                    keep_indices.add(i)
                    # Keep preceding lines (up to 3) for assertion context, pytest.raises, setups
                    for back in range(max(0, i - 3), i):
                        bs = block_tail[back].strip()
                        if bs and not re.match(r'^[=_-]{5,}$', bs):
                            keep_indices.add(back)
                # 3. Explicit pytest assertion / inspection markers
                elif any(m in s for m in ('pytest.raises', 'pytest.warns', 'match=')):
                    keep_indices.add(i)
                elif s.startswith(('assert ', 'assert(')) or ' assert ' in s:
                    keep_indices.add(i)
                elif re.match(r'^\s*[\^~]+\s*$', l):  # Caret underlines
                    keep_indices.add(i)
                elif re.match(r'^\w+[\w./\\-]*\.py:\d+:', s):  # Frame locations (e.g. test_task.py:9:)
                    keep_indices.add(i)
                elif s.startswith('#') or s.startswith('"""'):  # Comments or docstrings
                    keep_indices.add(i)

            body_lines = [l for i, l in enumerate(block_tail) if i in keep_indices]
        else:
            in_exc_msg = False
            last_file_frame = []
            body_lines = []
            for l in block[1:]:
                s = l.strip()
                if '--- [Captured output collapsed] ---' in l:
                    has_collapsed_stdout = True
                    continue
                if re.match(r'^\s*File\s+\".*?\",\s+line\s+\d+', l):
                    last_file_frame = [l]
                    in_exc_msg = False
                elif last_file_frame and not in_exc_msg and re.match(r'^\s*\w*(?:Error|Exception):', s):
                    body_lines.extend(last_file_frame)
                    last_file_frame = []
                    body_lines.append(l)
                    in_exc_msg = True
                elif in_exc_msg:
                    body_lines.append(l)
                elif last_file_frame:
                    last_file_frame.append(l)
            if not body_lines and last_file_frame:
                body_lines.extend(last_file_frame)
            if not body_lines:
                body_lines = [l for l in block[1:] if '--- [Captured output collapsed] ---' not in l]

        comp = header.copy()
        if len(block) > len(header) + len(body_lines) + 4:
            comp.append('    ... [intermediate frames omitted] ...')
        comp.extend(body_lines)
        if has_collapsed_stdout:
            comp.append('    --- [Captured output collapsed] ---')

        compressed_sections.append('\n'.join(comp))

    output_parts = ['\n'.join(compressed_sections)]
    if summary_lines:
        output_parts.append('\n'.join(summary_lines))

    proposed = '\n'.join(output_parts)

    # Fail-open diagnostic integrity guard
    def diagnostic_lines(value):
        return Counter(
            line.strip() for line in value.splitlines()
            if (line.lstrip().startswith(('E ', 'E\t', '> ', 'FAILED ', 'ERROR '))
                or line.strip() == 'E'
                or re.match(r'^[\w.]+(?:Error|Exception|Warning|Exit|Interrupt):', line.strip()))
        )

    original_evidence = diagnostic_lines(raw_log)
    compressed_evidence = diagnostic_lines(proposed)

    failure_header = re.compile(r'^_{3,}\s*.*?\s*_{3,}$')
    original_headers = Counter(
        l.strip() for l in raw_log.splitlines()
        if failure_header.match(l.strip())
    )
    compressed_headers = Counter(
        l.strip() for l in proposed.splitlines()
        if failure_header.match(l.strip())
    )
    if any(compressed_headers[line] < count for line, count in original_headers.items()):
        return raw_log
    if any(compressed_evidence[line] < count for line, count in original_evidence.items()):
        return raw_log

    return proposed

