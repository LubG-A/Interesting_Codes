#!/usr/bin/env python3
"""
Version Directory Scanner
扫描目录结构，发现存储历代版本的目录

识别特征：
1. 同一目录内存在大量名称类似但带有不同版本标识的子目录
2. 这些子目录内部的文件和子目录结构高度相似
"""

import os
import re
import sys
import argparse
from collections import defaultdict
from itertools import combinations


SUFFIX_PATTERNS = [
    re.compile(r'[_\-\s.]+v?\d+(\.\d+)*$', re.IGNORECASE),
    re.compile(r'[_\-\s.]+r\d+$', re.IGNORECASE),
    re.compile(r'[_\-\s.]+rev\.?\d+$', re.IGNORECASE),
    re.compile(r'[_\-\s.]+build\.?\d+$', re.IGNORECASE),
    re.compile(r'[_\-\s.]+\d{8}(_\d{6})?$', re.IGNORECASE),
    re.compile(r'[_\-\s.]+\d{4}[_\-]\d{2}[_\-]\d{2}([_T]\d{2}[_\-:]\d{2}([_\-:]\d{2})?)?$', re.IGNORECASE),
    re.compile(r'\s*\(\d+\)$'),
    re.compile(r'[_\-\s.]+copy\d*$', re.IGNORECASE),
    re.compile(r'[_\-\s.]+backup\d*$', re.IGNORECASE),
    re.compile(r'[_\-\s.]+bak\d*$', re.IGNORECASE),
    re.compile(r'[_\-\s.]+old\d*$', re.IGNORECASE),
]

PREFIX_PATTERNS = [
    re.compile(r'^v?\d+(\.\d+)*[_\-\s.]+', re.IGNORECASE),
]

INLINE_PATTERNS = [
    re.compile(r'[_\-\s.]v?\d+(\.\d+)+([_\-\s.]|$)', re.IGNORECASE),
    re.compile(r'[_\-\s.]r\d+([_\-\s.]|$)', re.IGNORECASE),
    re.compile(r'[_\-\s.]\d{8}([_\-\s.]|$)', re.IGNORECASE),
]

SKIP_DIRS = {
    '.git', '.svn', '.hg', 'node_modules', '__pycache__', '.idea', '.vscode',
    'venv', '.venv', 'env',
    'Windows', 'Program Files', 'Program Files (x86)', 'ProgramData',
    '$Recycle.Bin', '$Windows.~WS', '$Windows.~BT', 'Windows.old',
    'System Volume Information', 'Recovery', 'PerfLogs',
    'Intel', 'AMD', 'NVIDIA Corporation',
    'Microsoft.NET', 'Common Files',
}


def strip_version(name):
    for pattern in SUFFIX_PATTERNS:
        result = pattern.sub('', name)
        if result and result != name:
            return result, True
    for pattern in PREFIX_PATTERNS:
        result = pattern.sub('', name)
        if result and result != name:
            return result, True
    return name, False


def normalize_name(name):
    result = name
    for pattern in INLINE_PATTERNS:
        result = pattern.sub('\x00', result)
    return result


def get_dir_contents(dir_path, max_depth=2, _current_depth=0):
    files = set()
    subdirs = set()
    if _current_depth >= max_depth:
        return files, subdirs
    try:
        for entry in os.scandir(dir_path):
            if entry.is_file(follow_symlinks=False):
                files.add(entry.name)
            elif entry.is_dir(follow_symlinks=False):
                subdirs.add(entry.name)
                if _current_depth + 1 < max_depth:
                    sub_files, sub_dirs = get_dir_contents(
                        entry.path, max_depth, _current_depth + 1
                    )
                    for sf in sub_files:
                        files.add(os.path.join(entry.name, sf))
                    for sd in sub_dirs:
                        subdirs.add(os.path.join(entry.name, sd))
    except (PermissionError, OSError):
        pass
    return files, subdirs


def jaccard_similarity(set_a, set_b):
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def find_version_groups(dirnames):
    groups = defaultdict(list)
    assigned = set()

    for name in dirnames:
        base, matched = strip_version(name)
        if matched:
            groups[base].append(name)
            assigned.add(name)

    remaining = [n for n in dirnames if n not in assigned]
    if len(remaining) >= 2:
        norm_groups = defaultdict(list)
        for name in remaining:
            norm = normalize_name(name)
            if norm != name:
                norm_groups[norm].append(name)
        for norm, names in norm_groups.items():
            if len(names) >= 2:
                groups[norm].extend(names)
                assigned.update(names)

    still_remaining = [n for n in dirnames if n not in assigned]
    if len(still_remaining) >= 3:
        prefix_groups = _group_by_trailing_number(still_remaining)
        for prefix, names in prefix_groups.items():
            groups[f'~{prefix}'].extend(names)

    return {k: v for k, v in groups.items() if len(v) >= 2}


def _group_by_trailing_number(names):
    groups = defaultdict(list)
    for name in names:
        m = re.match(r'^(.*?)(\d+)$', name)
        if m and m.group(1):
            groups[m.group(1)].append(name)
    return {k: v for k, v in groups.items() if len(v) >= 3}


def compute_similarity(structures, dirs):
    similarities = []
    for d1, d2 in combinations(dirs, 2):
        files1, subdirs1 = structures[d1]
        files2, subdirs2 = structures[d2]

        file_sim = jaccard_similarity(files1, files2)
        subdir_sim = jaccard_similarity(subdirs1, subdirs2)

        has_files = bool(files1 or files2)
        has_subdirs = bool(subdirs1 or subdirs2)

        if has_files and has_subdirs:
            combined = file_sim * 0.6 + subdir_sim * 0.4
        elif has_files:
            combined = file_sim
        elif has_subdirs:
            combined = subdir_sim
        else:
            combined = 0.0

        similarities.append(combined)

    return similarities


def scan_directory(root_path, min_group_size=3, similarity_threshold=0.4, max_depth=2):
    results = []
    scanned_dirs = 0

    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        scanned_dirs += 1
        if not dirnames:
            continue

        groups = find_version_groups(dirnames)

        for base_name, dirs in groups.items():
            if len(dirs) < min_group_size:
                continue

            structures = {}
            for d in dirs:
                full_path = os.path.join(dirpath, d)
                files, subdirs = get_dir_contents(full_path, max_depth)
                structures[d] = (files, subdirs)

            similarities = compute_similarity(structures, dirs)

            if not similarities:
                continue

            avg_similarity = sum(similarities) / len(similarities)

            if avg_similarity >= similarity_threshold:
                all_files = [structures[d][0] for d in dirs]
                all_subdirs = [structures[d][1] for d in dirs]
                common_files = set.intersection(*all_files) if all_files else set()
                common_subdirs = set.intersection(*all_subdirs) if all_subdirs else set()

                results.append({
                    'parent': dirpath,
                    'base_name': base_name,
                    'version_dirs': sorted(dirs),
                    'count': len(dirs),
                    'avg_similarity': avg_similarity,
                    'min_similarity': min(similarities),
                    'common_files': sorted(common_files),
                    'common_subdirs': sorted(common_subdirs),
                })

    return results, scanned_dirs


def main():
    parser = argparse.ArgumentParser(
        description='扫描目录结构，发现存储历代版本的目录',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('path', help='要扫描的根目录路径')
    parser.add_argument('-n', '--min-group-size', type=int, default=3,
                        help='最小版本目录数量阈值 (默认: 3)')
    parser.add_argument('-s', '--similarity-threshold', type=float, default=0.4,
                        help='内容相似度阈值，0.0~1.0 (默认: 0.4)')
    parser.add_argument('-d', '--max-depth', type=int, default=2,
                        help='扫描子目录内容的最大深度 (默认: 2)')

    args = parser.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(f"错误: '{root}' 不是有效的目录路径", file=sys.stderr)
        sys.exit(1)

    args.similarity_threshold = max(0.0, min(1.0, args.similarity_threshold))

    print("=" * 50)
    print("  版本目录扫描工具 (Version Scanner)")
    print("=" * 50)
    print()
    print(f"  扫描路径:   {root}")
    print(f"  最小组大小: {args.min_group_size}")
    print(f"  相似度阈值: {args.similarity_threshold:.0%}")
    print(f"  扫描深度:   {args.max_depth}")
    print("-" * 50)

    results, scanned_dirs = scan_directory(
        root, args.min_group_size, args.similarity_threshold, args.max_depth
    )

    print(f"\n扫描完成: 共扫描 {scanned_dirs} 个目录")

    if not results:
        print("未发现版本目录")
        return

    results.sort(key=lambda x: (x['count'], x['avg_similarity']), reverse=True)

    print(f"发现 {len(results)} 组版本目录:\n")

    for i, r in enumerate(results, 1):
        print(f"+-- [{i}] 版本目录组 {'-' * 35}")
        print(f"| 位置:     {r['parent']}")
        print(f"| 基础名:   {r['base_name']}")
        print(f"| 版本数:   {r['count']}")
        print(f"| 相似度:   平均 {r['avg_similarity']:.1%} / 最低 {r['min_similarity']:.1%}")
        print(f"| 版本目录:")
        for d in r['version_dirs']:
            print(f"|   * {d}")
        if r['common_files']:
            shown = r['common_files'][:8]
            extra = len(r['common_files']) - len(shown)
            label = f"共有文件 ({len(r['common_files'])}个)"
            if extra > 0:
                label += f", 显示前{len(shown)}个"
            print(f"| {label}:")
            for f in shown:
                print(f"|   - {f}")
        if r['common_subdirs']:
            shown = r['common_subdirs'][:5]
            extra = len(r['common_subdirs']) - len(shown)
            label = f"共有子目录 ({len(r['common_subdirs'])}个)"
            if extra > 0:
                label += f", 显示前{len(shown)}个"
            print(f"| {label}:")
            for sd in shown:
                print(f"|   - {sd}")
        print(f"+{'-' * 49}")


if __name__ == '__main__':
    main()
