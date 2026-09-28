"""Audit bundled traces and optionally export one experiment; standard library only."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tarfile


def parse_trace(lines):
    labels, candidates, flows = [], [], []
    flow = None
    for number, raw in enumerate(lines, 1):
        parts = raw.decode('utf-8').split() if isinstance(raw, bytes) else raw.split()
        if not parts:
            continue
        tag, values = parts[0], parts[1:]
        if tag == 'Failing_link':
            labels.append({'src': int(values[0]), 'dst': int(values[1]), 'parameter_raw': float(values[2])})
        elif tag == 'FP':
            candidates.append(list(map(int, values)))
        elif tag == 'FID':
            if len(values) != 6:
                raise ValueError(f'Unexpected FID at line {number}')
            flow = dict(zip(('src', 'dst', 'src_rack', 'dst_rack', 'nbytes'), map(int, values[:5])))
            flow.update(flow_index=len(flows), start_time_ms=float(values[5]), snapshots=[], path_taken=None, reverse_path_taken=None)
            flows.append(flow)
        elif tag == 'SS':
            if flow is None or len(values) != 4:
                raise ValueError(f'Unexpected SS at line {number}')
            flow['snapshots'].append(dict(time_ms=float(values[0]), packets_sent=int(values[1]), packets_lost=int(values[2]), auxiliary_raw=int(values[3])))
        elif tag in ('FPT', 'FPRT'):
            if flow is None:
                raise ValueError(f'Path before FID at line {number}')
            flow['path_taken' if tag == 'FPT' else 'reverse_path_taken'] = list(map(int, values))
        else:
            raise ValueError(f'Unknown record {tag} at line {number}')
    return labels, candidates, flows


def topology_info(raw):
    edges, hosts = [], {}
    for line in raw.decode('utf-8').splitlines():
        if not line.strip():
            continue
        if '->' in line:
            host, rack = map(int, line.split('->'))
            hosts[host] = rack
        else:
            edges.append(list(map(int, line.split())))
    return {'switch_edges': edges, 'host_to_rack': hosts,
            'switch_count': len({n for e in edges for n in e}), 'host_count': len(hosts)}


def audit(archive, export_member=None, export_dir=None):
    records, totals, issues, groups = [], Counter(), Counter(), Counter()
    topo = None
    extra_files = []
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            if not member.isfile():
                continue
            if member.name.endswith('.edgelist'):
                topo = topology_info(tar.extractfile(member).read())
                continue
            if not Path(member.name).name.startswith('plog_'):
                extra_files.append({'member': member.name, 'bytes': member.size})
                continue
            with tar.extractfile(member) as source:
                labels, candidates, flows = parse_trace(source)
            times = []
            local_issues = Counter()
            for flow in flows:
                ss = flow['snapshots']
                times.extend(s['time_ms'] for s in ss)
                local_issues['missing_snapshots'] += not bool(ss)
                local_issues['missing_forward_path'] += flow['path_taken'] is None
                local_issues['missing_reverse_path'] += flow['reverse_path_taken'] is None
                local_issues['lost_gt_sent'] += sum(s['packets_lost'] > s['packets_sent'] for s in ss)
                local_issues['nonincreasing_snapshot_time'] += sum(b['time_ms'] <= a['time_ms'] for a, b in zip(ss, ss[1:]))
                local_issues['decreasing_sent_or_lost'] += sum(b['packets_sent'] < a['packets_sent'] or b['packets_lost'] < a['packets_lost'] for a, b in zip(ss, ss[1:]))
            name = Path(member.name).name
            fields = name.split('_')
            groups[f'{fields[1]} / filename_f={fields[2]} / label_count={len(labels)}'] += 1
            row = {'member': member.name, 'bytes': member.size, 'flows': len(flows), 'snapshots': len(times),
                   'candidate_paths': len(candidates), 'failed_links': labels,
                   'min_snapshot_ms': min(times) if times else None, 'max_snapshot_ms': max(times) if times else None,
                   'issues': dict(local_issues)}
            records.append(row)
            totals.update(experiments=1, flows=len(flows), snapshots=len(times), uncompressed_bytes=member.size)
            issues.update(local_issues)
            if export_member in (name, member.name):
                export_dir.mkdir(parents=True, exist_ok=True)
                with (export_dir / 'flows.jsonl').open('w', encoding='utf-8') as out:
                    for f in flows:
                        out.write(json.dumps(f) + '\n')
                metadata = {'archive': archive.name, **row, 'candidate_paths': candidates,
                            'auxiliary_semantics': 'max_delay_us (FLOW_DELAY mode)' if 'link_flap' in archive.name else 'raw field; C++ names it packets_randomly_lost'}
                (export_dir / 'experiment.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    if export_member and not any(export_member in (r['member'], Path(r['member']).name) for r in records):
        raise ValueError(f'Member not found: {export_member}')
    if export_member:
        (export_dir / 'topology.json').write_text(json.dumps(topo, indent=2), encoding='utf-8')
    with archive.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    return {'archive': archive.name, 'sha256': digest, 'extra_files': extra_files,
            'compressed_bytes': archive.stat().st_size, 'totals': dict(totals), 'groups': dict(sorted(groups.items())),
            'issues': dict(issues), 'topology': topo, 'experiments': records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='One archive; default audits all three')
    parser.add_argument('--out', type=Path, default=Path('data_analysis/inventory.json'))
    parser.add_argument('--export-member', help='Example: plog_skewed_1_0_14; requires --archive')
    parser.add_argument('--export-dir', type=Path, default=Path('data_analysis/example'))
    args = parser.parse_args()
    if args.export_member and not args.archive:
        parser.error('--export-member requires --archive')
    root = Path(__file__).resolve().parents[1]
    archives = [args.archive] if args.archive else sorted((root / 'hw_traces').glob('*.tar.gz'))
    result = []
    for archive in archives:
        item = audit(archive, args.export_member, args.export_dir)
        result.append(item)
        print(json.dumps({k: item[k] for k in ('archive', 'totals', 'groups', 'issues')}, ensure_ascii=False), flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
