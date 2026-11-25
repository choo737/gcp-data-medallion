"""Shared SHA-locked documentation & hygiene contract across all 5 choo737/gcp-* repositories.

Every repository in the suite MUST carry a byte-identical copy of this file at
`tests/suite_doc_contract.py`. `gcp-launchpad/scripts/audit-suite-uniformity.py`
verifies that all 5 repositories share the exact same SHA-256 digest and pass
every structural, table, navigation, agent-instruction, and prose-hygiene check.
"""

from __future__ import annotations

import re
from pathlib import Path

SUITE_REPOS: tuple[tuple[str, str, str], ...] = (
    ("gcp-launchpad", "00 Launchpad", "assets/cloud-city-launchpad.webp"),
    ("gcp-foundation", "01 Foundation", "assets/cloud-city-foundation.webp"),
    ("gcp-data-ingestion", "02 Ingestion", "assets/cloud-city-ingestion.webp"),
    ("gcp-data-medallion", "03 Medallion", "assets/cloud-city-medallion.webp"),
    ("gcp-data-science", "04 Data Science", "assets/cloud-city-data-science.webp"),
)

CANONICAL_README_H2_SECTIONS: list[str] = [
    "## Quick Orientation",
    "## Start in 3 Steps",
    "## Platform Districts",
    "## Technical Reference",
    "## License",
]

CANONICAL_DRAWER_SUMMARIES: tuple[str, ...] = (
    "<summary><strong>1. Architecture, Mermaid Flow & 2026 Product Naming</strong></summary>",
    "<summary><strong>2. Prerequisites, Keyless WIF CI/CD & Cost Guardrails</strong></summary>",
    "<summary><strong>3. Repository Layout, Agent Skills & Day-0 to Day-2 Guides</strong></summary>",
)

CANONICAL_DISTRICTS_HEADER = "| Repository | District & Layer | Core Capabilities | Status |"
CANONICAL_DISTRICTS_DIVIDER = "| --- | --- | --- | --- |"

# Canonical rows of the Platform Districts table (repo_name, district_col, capabilities_col, status_col)
CANONICAL_DISTRICT_ROWS: tuple[tuple[str, str, str, str], ...] = (
    (
        "gcp-launchpad",
        "`00` City Planning Hub",
        "Intake Q&A, preflight check, and Brownfield bridge",
        "Active",
    ),
    (
        "gcp-foundation",
        "`01` Governance & Utilities",
        "Folders, 38 Org Policies, Shared VPC, VPC-SC, KMS, and SCC",
        "Active",
    ),
    (
        "gcp-data-ingestion",
        "`02` Entry Ports & Bridges",
        "Pub/Sub + DLQ, Datastream CDC, Cloud Run jobs, and Workflows",
        "Active",
    ),
    (
        "gcp-data-medallion",
        "`03` Warehouses & Quality",
        "BigQuery Bronze/Silver/Gold, Dataform, and Knowledge Catalog",
        "Active",
    ),
    (
        "gcp-data-science",
        "`04` Offices, AI & Homes",
        "Agent Platform, BigQuery ML, TreeSHAP XAI, and WORM ledger",
        "Active",
    ),
    (
        "gcp-webapp",
        "Hosted App Template",
        "HTTPS Load Balancer, Cloud Armor, Cloud Run, and Cloud SQL",
        "Roadmap",
    ),
    (
        "gcp-adk-agent",
        "Hosted Agent Template",
        "Google ADK on Agent Runtime or Cloud Run with eval gates",
        "Roadmap",
    ),
)

CANONICAL_LICENSE_LINE = "Apache License 2.0. See [LICENSE](LICENSE)."
CANONICAL_DISCLAIMER_LINE = "**Disclaimer:** This is a personal project. The views, code, and opinions expressed are my own and do not represent my current or past employers."

TWELVE_DIGIT_RE = re.compile(r"(?<![A-Za-z0-9_-])\d{12}(?![A-Za-z0-9_-])")
BILLING_ID_RE = re.compile(r"\b[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}\b")
DEPRECATED_MODEL_RE = re.compile(
    r"\b(?:gemini-(?:1\.0|1\.5|2\.0|2\.5)|text-bison|chat-bison|code-bison|claude-[123]|gemma-[12])\b",
    re.IGNORECASE,
)
WORD_TOKEN_RE = re.compile(r"[A-Za-z0-9_'-]+")
BULLET_PREFIX_RE = re.compile(r"^(?:[-*+]|\d+\.)\s+")
MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]+\)")
ABBREV_DOT_RE = re.compile(r"\b(e|i)\.(g|e)\.", re.IGNORECASE)
TABLE_SEP_CELL_RE = re.compile(r"^:?-{3,}:?$")


def expected_breadcrumb_line(current_repo: str) -> str:
    parts: list[str] = []
    for repo_slug, label, _ in SUITE_REPOS:
        if repo_slug == current_repo:
            parts.append(f"**{label}**")
        else:
            parts.append(f"[{label}](https://github.com/choo737/{repo_slug})")
    return " · ".join(parts)


def expected_district_row_line(current_repo: str, row_spec: tuple[str, str, str, str]) -> str:
    repo_slug, district_col, cap_col, status_col = row_spec
    if status_col == "Roadmap":
        repo_cell = f"`{repo_slug}` *(Planned)*"
    elif repo_slug == current_repo:
        repo_cell = f"**{repo_slug}** *(this repo)*"
    else:
        repo_cell = f"[{repo_slug}](https://github.com/choo737/{repo_slug})"
    return f"| {repo_cell} | {district_col} | {cap_col} | {status_col} |"


def _strip_md_links(text: str) -> str:
    return MD_LINK_RE.sub(r"\1", text)


def extract_markdown_sentences_and_cells(md_text: str) -> tuple[list[str], list[str]]:
    lines = md_text.splitlines()
    in_code = False
    in_frontmatter = False
    prose_blocks: list[str] = []
    current_para: list[str] = []
    cells: list[str] = []

    def flush_para() -> None:
        if current_para:
            prose_blocks.append(" ".join(current_para))
            current_para.clear()

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if idx == 0 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue
        if stripped.startswith("```"):
            flush_para()
            in_code = not in_code
            continue
        if in_code:
            continue
        if stripped.startswith("|"):
            flush_para()
            raw_cells = [c.strip() for c in stripped.strip("|").split("|")]
            if raw_cells and all(TABLE_SEP_CELL_RE.match(c) for c in raw_cells if c):
                continue
            for cell in raw_cells:
                cleaned_cell = _strip_md_links(cell).strip()
                if cleaned_cell:
                    cells.append(cleaned_cell)
            continue
        if (
            not stripped
            or stripped.startswith(
                (
                    "#",
                    "---",
                    "<!--",
                    "<details",
                    "</details",
                    "<summary",
                    "<picture",
                    "</picture",
                    "<source",
                    "<img",
                    "![",
                )
            )
        ):
            flush_para()
            continue
        if stripped.startswith(">"):
            stripped = stripped.lstrip("> ").strip()
            if not stripped or stripped.startswith("[!"):
                flush_para()
                continue
        stripped = _strip_md_links(stripped)
        if BULLET_PREFIX_RE.match(stripped):
            flush_para()
            current_para.append(BULLET_PREFIX_RE.sub("", stripped).strip())
            continue
        current_para.append(stripped)

    flush_para()

    sentences: list[str] = []
    for block in prose_blocks:
        masked = ABBREV_DOT_RE.sub(lambda m: f"{m.group(1)}<DOT>{m.group(2)}<DOT>", block)
        for part in re.split(r"[.!?](?:\s+|$)", masked):
            cleaned = part.replace("<DOT>", ".").strip()
            if cleaned:
                sentences.append(cleaned)
    return sentences, cells


def validate_repo_suite_contract(repo_root: Path, repo_name: str) -> list[str]:
    """Returns a list of human-readable contract violations (empty list == 100% compliant)."""
    errors: list[str] = []
    repo_meta = {r[0]: r for r in SUITE_REPOS}
    if repo_name not in repo_meta:
        return [f"Unknown suite repository: {repo_name}"]
    _, _, hero_asset_rel = repo_meta[repo_name]

    # 1. Required root documentation files & forbidden legacy files
    for req in ("README.md", "QUESTIONNAIRE.md", "AGENTS.md", "CLAUDE.md", "CODEOWNERS", "LICENSE", "SECURITY.md", "Makefile", "tests/suite_doc_contract.py"):
        if not (repo_root / req).is_file():
            errors.append(f"Missing required file: {req}")
    for forbidden in ("GEMINI.md", "catalog.yaml"):
        if (repo_root / forbidden).exists():
            errors.append(f"Forbidden file present: {forbidden}")

    readme_path = repo_root / "README.md"
    if not readme_path.is_file():
        return errors
    readme = readme_path.read_text(encoding="utf-8")
    lines = readme.splitlines()

    # 2. Line 1 Suite Navigation Breadcrumb Bar
    exp_nav = expected_breadcrumb_line(repo_name)
    if not lines or lines[0].strip() != exp_nav:
        errors.append(f"README.md line 1 must equal canonical suite nav bar:\n  expected: {exp_nav}\n  actual:   {lines[0] if lines else '<empty>'}")

    # 3. Hero image tag syntax (<img src="assets/..." alt="..." width="100%">)
    hero_re = re.compile(rf'^<img src="{re.escape(hero_asset_rel)}" alt="[^"]+" width="100%">$', re.MULTILINE)
    if not hero_re.search(readme):
        errors.append(f'README.md missing canonical hero tag: <img src="{hero_asset_rel}" alt="..." width="100%">')

    # 4. Canonical 5-Act H2 sections in exact order (outside fenced code blocks)
    h2s: list[str] = []
    in_fence = False
    for ln in lines:
        if ln.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and ln.startswith("## "):
            h2s.append(ln.strip())
    if h2s != CANONICAL_README_H2_SECTIONS:
        errors.append(f"README.md H2 sections mismatch:\n  expected: {CANONICAL_README_H2_SECTIONS}\n  actual:   {h2s}")

    # 5. Private clone snippet uses canonical example-org + cd + isPrivate check
    expected_clone = f"gh repo create example-org/{repo_name} --private --template choo737/{repo_name} --clone"
    if expected_clone not in readme:
        errors.append(f"README.md missing canonical clone command: {expected_clone}")
    if "gh repo view --json isPrivate --jq '.isPrivate'" not in readme:
        errors.append("README.md missing 'gh repo view --json isPrivate --jq \'.isPrivate\'' verification line")
    if "acme-corp/" in readme or "<org>/" in readme:
        errors.append("README.md uses non-standard org placeholder ('acme-corp/' or '<org>/'); use 'example-org/'")

    # 6. Identical Platform Districts table across all 5 repos
    if CANONICAL_DISTRICTS_HEADER not in readme or CANONICAL_DISTRICTS_DIVIDER not in readme:
        errors.append("README.md missing canonical Platform Districts table header/divider")
    for row_spec in CANONICAL_DISTRICT_ROWS:
        exp_row = expected_district_row_line(repo_name, row_spec)
        if exp_row not in readme:
            errors.append(f"README.md missing canonical Platform Districts row:\n  expected: {exp_row}")

    # 7. Exact 3 expanded-by-default <details open> drawers in Technical Reference
    for summary_html in CANONICAL_DRAWER_SUMMARIES:
        if summary_html not in readme:
            errors.append(f"README.md missing canonical drawer summary: {summary_html}")
    if "<details>" in readme:
        errors.append("README.md contains collapsed <details>; use <details open> so sections expand by default")
    if readme.count("<details open>") != 3 or readme.count("</details>") != 3:
        errors.append(
            f"README.md must have exactly 3 <details open> drawers (found {readme.count('<details open>')})"
        )

    # 8. Canonical License & Personal Project Disclaimer lines
    if CANONICAL_LICENSE_LINE not in readme:
        errors.append(f"README.md missing canonical license line: {CANONICAL_LICENSE_LINE}")
    if CANONICAL_DISCLAIMER_LINE not in readme:
        errors.append(f"README.md missing canonical personal disclaimer line: {CANONICAL_DISCLAIMER_LINE}")

    # 9. AGENTS.md & CLAUDE.md uniform headers, cross-repo sync rule, and sequential step numbering
    agents_md = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
    claude_md = (repo_root / "CLAUDE.md").read_text(encoding="utf-8")
    if not agents_md.startswith("# AGENTS.md\n"):
        errors.append("AGENTS.md must start with '# AGENTS.md'")
    if "## Cross-Repo Documentation Invariant" not in agents_md:
        errors.append("AGENTS.md missing '## Cross-Repo Documentation Invariant' section")
    if "suite_doc_contract.py" not in agents_md or "audit-suite-uniformity.py" not in agents_md:
        errors.append("AGENTS.md must reference suite_doc_contract.py and audit-suite-uniformity.py")

    # Check numbered lists in AGENTS.md are strictly sequential (1, 2, 3...) per list block
    seq_expected = 1
    in_list = False
    in_code = False
    for idx_ln, ln in enumerate(agents_md.splitlines(), start=1):
        st = ln.strip()
        if st.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r"^(\d+)\.\s+", st)
        if m:
            num = int(m.group(1))
            if not in_list:
                in_list = True
                seq_expected = 1
            if num != seq_expected:
                errors.append(f"AGENTS.md:{idx_ln} broken step numbering (expected {seq_expected}., found {num}.)")
            seq_expected += 1
        elif not st or st.startswith("#"):
            in_list = False

    if not claude_md.startswith("# CLAUDE.md\n"):
        errors.append("CLAUDE.md must start with '# CLAUDE.md'")
    if "## Quick Rules" not in claude_md:
        errors.append("CLAUDE.md missing '## Quick Rules' heading")
    if "AGENTS.md" not in claude_md or "suite_doc_contract.py" not in claude_md:
        errors.append("CLAUDE.md must reference AGENTS.md and suite_doc_contract.py")

    # 10. QUESTIONNAIRE.md uniform '## Section N:' headings & no stray '---' horizontal rules
    q_md = (repo_root / "QUESTIONNAIRE.md").read_text(encoding="utf-8")
    q_in_fence = False
    q_sections: list[str] = []
    for idx_ln, ln in enumerate(q_md.splitlines(), start=1):
        st = ln.strip()
        if st.startswith("```"):
            q_in_fence = not q_in_fence
            continue
        if q_in_fence:
            continue
        if st == "---":
            errors.append(f"QUESTIONNAIRE.md:{idx_ln} contains non-standard '---' horizontal divider")
        if re.match(r"^##\s+\d+\.", st):
            errors.append(f"QUESTIONNAIRE.md:{idx_ln} uses '## N.' instead of '## Section N:': {st}")
        if st.startswith("## Section "):
            q_sections.append(st)
    if not q_sections:
        errors.append("QUESTIONNAIRE.md must contain '## Section 1:'.. headings")
    if repo_name != "gcp-launchpad" and "## Handoff From Launchpad" not in q_md:
        errors.append("Downstream QUESTIONNAIRE.md must contain '## Handoff From Launchpad'")

    # 11. Makefile must define 'help' and 'test' targets
    makefile_txt = (repo_root / "Makefile").read_text(encoding="utf-8")
    for target in ("help:", "test:"):
        if not re.search(rf"^{re.escape(target)}", makefile_txt, flags=re.MULTILINE):
            errors.append(f"Makefile missing standard target '{target[:-1]}'")

    # 12. Markdown <= 20-word sentence & table-cell cap + anti-leak + deprecated-model scan across ALL .md files
    for md_path in sorted(repo_root.rglob("*.md")):
        if any(part in {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", ".terraform"} for part in md_path.parts):
            continue
        rel = str(md_path.relative_to(repo_root))
        txt = md_path.read_text(encoding="utf-8")
        if TWELVE_DIGIT_RE.search(txt):
            errors.append(f"{rel}: contains literal 12-digit number")
        if BILLING_ID_RE.search(txt):
            errors.append(f"{rel}: contains hex billing ID pattern")
        if DEPRECATED_MODEL_RE.search(txt):
            errors.append(f"{rel}: contains deprecated model identifier")
        sents, tbl_cells = extract_markdown_sentences_and_cells(txt)
        for s in sents:
            toks = WORD_TOKEN_RE.findall(s)
            if len(toks) > 20:
                errors.append(f"{rel}: sentence > 20 words ({len(toks)} tokens): {s}")
        for c in tbl_cells:
            toks = WORD_TOKEN_RE.findall(c)
            if len(toks) > 20:
                errors.append(f"{rel}: table cell > 20 words ({len(toks)} tokens): {c}")

    return errors
