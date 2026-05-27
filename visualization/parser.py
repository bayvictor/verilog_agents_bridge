"""Verilog-A file parser — extracts structural elements into dataclasses."""

import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class Port:
    name: str
    direction: str   # 'input' | 'output' | 'inout'
    discipline: str = 'electrical'


@dataclass
class Parameter:
    name: str
    ptype: str       # 'real' | 'integer' | 'string'
    default: str = ''


@dataclass
class Branch:
    name: str
    node_plus: str
    node_minus: str = ''


@dataclass
class Contribution:
    nature: str      # 'V' | 'I'
    target: str
    expression: str


@dataclass
class Instance:
    module_name: str
    inst_name: str
    connections: List[str] = field(default_factory=list)


@dataclass
class VerilogAModule:
    name: str
    port_names: List[str] = field(default_factory=list)
    ports: List[Port] = field(default_factory=list)
    parameters: List[Parameter] = field(default_factory=list)
    nets: List[str] = field(default_factory=list)
    branches: List[Branch] = field(default_factory=list)
    contributions: List[Contribution] = field(default_factory=list)
    instances: List[Instance] = field(default_factory=list)


_DISCIPLINES = frozenset({
    'electrical', 'voltage', 'current', 'magnetic', 'thermal',
    'mechanical', 'kinematic', 'kinematic_v', 'logic',
})

_KEYWORDS = frozenset({
    'module', 'endmodule', 'analog', 'begin', 'end', 'if', 'else', 'for',
    'while', 'case', 'casex', 'casez', 'endcase', 'parameter', 'localparam',
    'electrical', 'branch', 'real', 'integer', 'string', 'genvar',
    'input', 'output', 'inout', 'wire', 'reg', 'supply0', 'supply1',
    'initial', 'always', 'assign', 'function', 'endfunction', 'task',
    'endtask', 'generate', 'endgenerate', 'specify', 'endspecify',
})


def _strip_comments(source: str) -> str:
    """Remove /* */ and // comments, preserving newlines for line numbering."""
    source = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group().count('\n'), source, flags=re.DOTALL)
    source = re.sub(r'//[^\n]*', '', source)
    return source


def _parse_portlist(s: str) -> List[str]:
    s = s.strip().strip('()')
    return [p.strip() for p in s.split(',') if p.strip()]


def _names_from(s: str) -> List[str]:
    return [n.strip() for n in s.split(',') if n.strip()]


def _parse_body(body: str, mod: VerilogAModule) -> None:
    # ── Port directions ──────────────────────────────────────────────────────
    for direction in ('input', 'output', 'inout'):
        pat = re.compile(
            rf'\b{direction}\b\s+'
            rf'(?:(?P<disc>[A-Za-z_]\w*)\s+)?'
            rf'(?P<names>(?:\w+\s*,\s*)*\w+)\s*;'
        )
        for m in pat.finditer(body):
            disc = m.group('disc') or 'electrical'
            names_str = m.group('names')
            if disc not in _DISCIPLINES:
                # treat disc token as first port name, no explicit discipline
                names_str = disc + ',' + names_str
                disc = 'electrical'
            for name in _names_from(names_str):
                if not any(p.name == name for p in mod.ports):
                    mod.ports.append(Port(name=name, direction=direction, discipline=disc))

    # ── Parameters ──────────────────────────────────────────────────────────
    param_re = re.compile(
        r'\bparameter\b\s+(?:(?P<type>real|integer|string)\s+)?'
        r'(?P<name>\w+)\s*=\s*(?P<val>[^;]+?)'
        r'(?:\s+from\s+\S+)?\s*;'
    )
    for m in param_re.finditer(body):
        mod.parameters.append(Parameter(
            name=m.group('name'),
            ptype=m.group('type') or 'real',
            default=m.group('val').strip(),
        ))

    # ── Electrical net declarations ──────────────────────────────────────────
    elec_re = re.compile(r'\belectrical\b\s+((?:\w+\s*,\s*)*\w+)\s*;')
    for m in elec_re.finditer(body):
        for n in _names_from(m.group(1)):
            if n not in mod.nets:
                mod.nets.append(n)

    # ── Branch declarations ──────────────────────────────────────────────────
    branch_re = re.compile(r'\bbranch\b\s*\(([^)]+)\)\s+((?:\w+\s*,\s*)*\w+)\s*;')
    for m in branch_re.finditer(body):
        nodes = [n.strip() for n in m.group(1).split(',')]
        n_plus = nodes[0] if nodes else ''
        n_minus = nodes[1] if len(nodes) > 1 else ''
        for name in _names_from(m.group(2)):
            mod.branches.append(Branch(name=name, node_plus=n_plus, node_minus=n_minus))

    # ── Analog contributions  V(...) <+ ...; or I(...) <+ ...; ──────────────
    contrib_re = re.compile(r'\b([VI])\(([^)]+)\)\s*<\+\s*([^;]+?)\s*;')
    for m in contrib_re.finditer(body):
        expr = m.group(3).strip()
        if len(expr) > 64:
            expr = expr[:61] + '...'
        mod.contributions.append(Contribution(
            nature=m.group(1),
            target=m.group(2).strip(),
            expression=expr,
        ))

    # ── Module instances (heuristic) ─────────────────────────────────────────
    inst_re = re.compile(r'\b(\w+)\s+(\w+)\s*\(([^)]*)\)\s*;')
    for m in inst_re.finditer(body):
        mname, iname = m.group(1), m.group(2)
        if mname not in _KEYWORDS and iname not in _KEYWORDS:
            conns = [c.strip() for c in m.group(3).split(',') if c.strip()]
            mod.instances.append(Instance(module_name=mname, inst_name=iname, connections=conns))


def parse_source(source: str) -> List[VerilogAModule]:
    """Parse a Verilog-A source string; return list of modules found."""
    modules: List[VerilogAModule] = []
    clean = _strip_comments(source)
    module_re = re.compile(
        r'\bmodule\s+(\w+)\s*(\([^)]*\))?\s*;(.*?)\bendmodule\b',
        re.DOTALL,
    )
    for m in module_re.finditer(clean):
        mod = VerilogAModule(
            name=m.group(1),
            port_names=_parse_portlist(m.group(2) or ''),
        )
        _parse_body(m.group(3), mod)
        modules.append(mod)
    return modules


def parse_file(filepath: str) -> List[VerilogAModule]:
    """Parse a Verilog-A file; return list of modules found."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as fh:
        return parse_source(fh.read())
