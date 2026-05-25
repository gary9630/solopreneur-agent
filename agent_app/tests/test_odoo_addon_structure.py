import ast
from pathlib import Path
from xml.etree import ElementTree


REPO_ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = REPO_ROOT / "odoo_addons" / "deal_to_delivery_agent"


def load_manifest() -> dict:
    manifest_path = ADDON_ROOT / "__manifest__.py"

    assert manifest_path.exists()
    return ast.literal_eval(manifest_path.read_text(encoding="utf-8"))


def test_manifest_matches_mvp_addon_contract():
    manifest = load_manifest()

    assert manifest["name"] == "Deal-to-Delivery Agent Bridge"
    assert manifest["version"] == "0.1.0"
    assert manifest["category"] == "Productivity"
    assert manifest["summary"] == "Agent bridge for SME deal-to-delivery automation"
    assert manifest["depends"] == ["base", "crm", "sale", "project", "account"]
    assert manifest["data"] == [
        "data/demo_products.xml",
        "views/agent_audit_log_views.xml",
        "views/deal_context_views.xml",
    ]
    assert manifest["installable"] is True
    assert manifest["application"] is False
    assert manifest["license"] == "LGPL-3"


def test_model_files_exist_without_requiring_odoo_imports():
    expected_paths = [
        ADDON_ROOT / "__init__.py",
        ADDON_ROOT / "models" / "__init__.py",
        ADDON_ROOT / "models" / "agent_audit_log.py",
        ADDON_ROOT / "models" / "deal_context.py",
    ]

    for path in expected_paths:
        assert path.exists(), f"missing {path.relative_to(REPO_ROOT)}"


def test_odoo_xml_files_are_well_formed():
    xml_paths = [
        ADDON_ROOT / "data" / "demo_products.xml",
        ADDON_ROOT / "views" / "agent_audit_log_views.xml",
        ADDON_ROOT / "views" / "deal_context_views.xml",
    ]

    for path in xml_paths:
        tree = ElementTree.parse(path)

        assert tree.getroot().tag == "odoo"
