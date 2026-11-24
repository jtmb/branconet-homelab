"""Validate and serve only BORTUS planning artifacts, without disk spooling."""

import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import re
import ssl
from urllib.parse import urlsplit
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet._writer import WorksheetWriter
from openpyxl.writer.excel import ExcelWriter


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOCS = HERE.parent / "operations"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class MemoryExcel(ExcelWriter):
    """Write worksheet XML into memory instead of openpyxl's default tempfile."""

    def write_worksheet(self, sheet):
        """Archive plain worksheets; this export does not handle drawings."""
        data = BytesIO()
        assert not sheet._charts and not sheet._images
        writer = WorksheetWriter(sheet, out=data)
        writer.write()
        sheet._rels = writer._rels
        self._archive.writestr(sheet.path[1:], data.getvalue())
        self.manifest.append(sheet)


def format_sheet(sheet, widths, row_height):
    """Make derived sheets readable without filtering out any requirements."""
    sheet.freeze_panes = "B2"
    for column, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(column)].width = width
    for row in sheet.iter_rows():
        sheet.row_dimensions[row[0].row].height = 28 if row[0].row == 1 else row_height
        for cell in row:
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            if cell.row == 1:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="254569")


def workbook(records, cost=False):
    """Make one editable workbook and reload it before allowing delivery."""
    book = Workbook()
    sheet = book.active
    if cost:
        sheet.title = "Cost inputs and estimates"
        sheet.append(["Scenario", "Runs/month", "Seconds/run", "vCPU cap", "RAM MiB",
                      "Cached images GiB", "Setup labor h", "Transfer MiB/run",
                      "vCPU h/month", "Transfer MiB/month", "Labor USD/h", "Labor USD"])
        for row, item in enumerate(records["cost_model"]["scenarios"], 2):
            sheet.append([*item.values(), f"=B{row}*C{row}*D{row}/3600",
                          f"=B{row}*H{row}", None,
                          f'=IF(K{row}="","Unpriced",G{row}*K{row})'])
            sheet[f"I{row}"].number_format = "0.00"
        format_sheet(sheet, [16, 13, 13, 12, 12, 15, 15, 15, 15, 15, 14, 13], 32)
    else:
        sheet.title = "Requirements"
        sheet.append(["ID", "Requirement", "Scope", "Status", "Work", "Gate", "Owner",
                      "Acceptance", "Reviewer", "Evidence", "Revision", "Review note (proposal)"])
        for item in records["requirements"]:
            sheet.append([item[key] for key in ("id", "requirement", "scope", "state",
                          "work", "gate", "owner", "acceptance", "reviewer", "evidence",
                          "tested_revision")])
        sheet.auto_filter.ref = f"A1:L{sheet.max_row}"
        format_sheet(sheet, [9, 45, 23, 12, 10, 10, 22, 65, 22, 22, 15, 24], 55)
        gates = book.create_sheet("Release gates")
        gates.append(["Gate", "Work", "Status", "Depends on", "Evidence"])
        for gate in records["gates"]:
            gates.append([gate["id"], gate["work"], gate["state"],
                          ", ".join(gate["depends"]), gate["evidence"]])
        format_sheet(gates, [12, 12, 14, 16, 50], 25)
        if records.get("accepted_residuals"):
            sheet = book.create_sheet("Accepted residuals")
            sheet.append(["ID", "Constrains", "Statement", "Impact", "Owner",
                          "Accepted", "Reconsider when", "Evidence"])
            for item in records["accepted_residuals"]:
                sheet.append([item["id"], ", ".join([item["gate"], *item["requirements"]]),
                              item["statement"], item["impact"], item["owner"],
                              item["accepted"], item["reconsideration"], item["evidence"]])
            format_sheet(sheet, [8, 16, 55, 55, 20, 12, 55, 45], 70)
    notes = book.create_sheet("Read me")
    notes.append(["Canonical source", "Instructions"])
    notes.append(["records.json", records["cost_model"]["notes"] if cost else
                  "Review notes propose changes only. Give stable ID, expected old value, "
                  "suggested change, evidence and reviewer to the integrator. The integrator "
                  "resolves conflicts against the current JSON, then regenerates this view."])
    notes.append(["Date", records["as_of"]])
    format_sheet(notes, [25, 98], 44)
    output = BytesIO()
    MemoryExcel(book, ZipFile(output, "w", ZIP_DEFLATED)).save()
    payload = output.getvalue()
    checked = load_workbook(BytesIO(payload))
    actual = checked.worksheets[0]
    if cost:
        assert actual["I3"].value == "=B3*C3*D3/3600"
        assert actual["J3"].value == "=B3*H3" and actual["K3"].value is None
        assert actual["L3"].value == '=IF(K3="","Unpriced",G3*K3)'
        assert (actual["B3"].value * actual["C3"].value / 3600,
                actual["B3"].value * actual["H3"].value) == (2 / 3, 120)
    else:
        assert [row[0] for row in list(actual.values)[1:]] == [
            item["id"] for item in records["requirements"]]
        assert [row[2] for row in list(checked["Release gates"].values)[1:]] == [
            item["state"] for item in records["gates"]]
        if records.get("accepted_residuals"):
            residual = list(checked["Accepted residuals"].values)[1]
            assert residual[0] == records["accepted_residuals"][0]["id"]
            assert residual[3], "residual impact must be present"
    return payload


def package():
    """Check plan traceability, then return versioned inputs and derived artifacts."""
    records = json.loads((HERE / "records.json").read_text())
    docs = sorted(DOCS.glob("0[0-7]_*.md"))
    assert len(docs) == 8
    buckets = ("scope_history", "requirements", "decisions", "dependencies",
               "assumptions", "sources", "gates")
    ids = [row["id"] for bucket in buckets for row in records[bucket]]
    assert len(ids) == len(set(ids))
    gates = {item["id"]: item for item in records["gates"]}
    roadmap = docs[7].read_text()
    for row in records["requirements"]:
        assert (DOCS / row["spec"]).is_file()
        assert row["source"] in ids and set(row["depends"]) <= set(ids)
        assert gates[row["gate"]]["work"] == row["work"] and row["work"] in roadmap
        assert row["state"] in ("planned", "partial", "verified", "accepted")
        if row["state"] == "planned":
            assert row["evidence"] is None
        else:
            assert (ROOT / row["evidence"]).is_file(), row["id"]
    for index, gate in enumerate(gates.values()):
        assert all(item in list(gates)[:index] for item in gate["depends"])
        assert gate["state"] in ("pending", "partial", "passed", "accepted")
        if gate["state"] != "pending":
            assert (ROOT / gate["evidence"]).is_file(), gate["id"]
    # An accepted gate or requirement must name a residual that explains it.
    residual_ids = set()
    for residual in records.get("accepted_residuals", []):
        assert (ROOT / residual["evidence"]).is_file(), residual["id"]
        assert residual["owner"] and residual["reconsideration"] and residual["accepted"]
        residual_ids.add(residual["gate"])
        residual_ids.update(residual["requirements"])
    for item in [*records["requirements"], *records["gates"]]:
        if item["state"] == "accepted":
            assert item["id"] in residual_ids, item["id"]
    for change in records["scope_history"]:
        assert set(change["affected"]) <= set(ids)
    for visual in records["visuals"]:
        assert set(visual["requirements"]) <= set(ids)
        assert ElementTree.parse(HERE / visual["file"]).getroot().tag.endswith("}svg")
    derived = {"acceptance_tracker.xlsx": workbook(records),
               "cost-model.xlsx": workbook(records, cost=True)}
    handoff = ROOT / "docs/memory/08_BORTUS_MCP_HANDOFF.txt"
    evidence = ROOT / "docs/planning/evidence/2026-11-18-bortus-mcp-implementation.md"
    paths = [*docs, handoff, evidence, *[HERE / item for item in (
        "records.json", "VALIDATION.md", "flow.svg", "export_plan.py")]]
    for path in paths:
        assert path.stat().st_size < 100_000
        if path.suffix == ".md":
            for href in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if not urlsplit(href).scheme:
                    assert (path.parent / href).resolve() in paths, (path, href)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for path in paths:
            archive.writestr(path.relative_to(ROOT).as_posix(), path.read_bytes())
        for name, data in derived.items():
            archive.writestr((HERE / name).relative_to(ROOT).as_posix(), data)
    with ZipFile(BytesIO(buffer.getvalue())) as archive:
        assert archive.testzip() is None and len(archive.namelist()) == len(paths) + len(derived)
    return paths, derived | {"bortus-mcp-plan.zip": buffer.getvalue()}


def serve(args, paths, outputs):
    """Reuse the approved Markdown renderer; serve only an exact immutable route map."""
    spec = importlib.util.spec_from_file_location("artifact_renderer", args.renderer)
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    names = {path: ("bortus-mcp-plan.html" if path.name.startswith("00_") else
                    path.with_suffix(".html").name if path.suffix == ".md" else path.name)
             for path in paths if path.suffix != ".py"}
    urls = {path: f"https://localhost:{args.port}/{name}" for path, name in names.items()}
    urls.update({HERE / name: f"https://localhost:{args.port}/{name}" for name in outputs})
    types = {".md": "text/html; charset=utf-8", ".txt": "text/plain; charset=utf-8",
             ".svg": "image/svg+xml", ".json": "application/json"}
    routes = {name: (types[path.suffix],
                     renderer.page(path, urls) if path.suffix == ".md" else path.read_bytes())
              for path, name in names.items()}
    for name, data in outputs.items():
        routes[name] = ("application/zip" if name.endswith(".zip") else XLSX, data)

    class Handler(BaseHTTPRequestHandler):
        """Send only explicit artifacts; no file browsing or request logging."""

        def do_GET(self):
            """Reject unlisted paths and supply cache/TLS-safe artifact metadata."""
            name = urlsplit(self.path).path.removeprefix("/")
            if name not in routes:
                self.send_error(404)
                return
            kind, data = routes[name]
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; frame-ancestors 'none'")
            if kind in (XLSX, "application/zip"):
                self.send_header("Content-Disposition", f'attachment; filename="{escape(name)}"')
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args):
            """Do not create access logs for this loopback delivery."""

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.cert, args.key)
    with HTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.socket = context.wrap_socket(server.socket, server_side=True)
        print(f"Serving {len(routes)} exact in-memory routes on localhost:{args.port}", flush=True)
        server.serve_forever()


def main():
    """Run stand-alone package checks, optionally start the owned HTTPS preview."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int)
    parser.add_argument("--cert")
    parser.add_argument("--key")
    parser.add_argument("--renderer")
    args = parser.parse_args()
    paths, outputs = package()
    records = json.loads((HERE / "records.json").read_text())
    states = {}
    for gate in records["gates"]:
        states[gate["state"]] = states.get(gate["state"], 0) + 1
    print(f"Validated {len(paths)} sources, {len(records['requirements'])} mapped requirements, "
          f"gates {states}, 2 reloaded XLSX workbooks and "
          f"{len(outputs['bortus-mcp-plan.zip'])} ZIP bytes", flush=True)
    if args.port:
        if not all((args.cert, args.key, args.renderer)):
            parser.error("serving requires certificate, key and artifact renderer")
        serve(args, paths, outputs)


if __name__ == "__main__":
    main()
