import ast
import csv
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
    required_data_files = [
        "security/ir.model.access.csv",
        "data/demo_products.xml",
        "views/agent_audit_log_views.xml",
        "views/deal_context_views.xml",
        "views/deal_agent_menus.xml",
    ]
    for data_file in required_data_files:
        assert data_file in manifest["data"]

    assert manifest["data"].index("security/ir.model.access.csv") == 0
    assert manifest["data"].index("views/deal_agent_menus.xml") > manifest["data"].index(
        "views/agent_audit_log_views.xml"
    )
    assert manifest["data"].index("views/deal_agent_menus.xml") > manifest["data"].index(
        "views/deal_context_views.xml"
    )
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
        ADDON_ROOT / "views" / "deal_agent_menus.xml",
    ]

    for path in xml_paths:
        tree = ElementTree.parse(path)

        assert tree.getroot().tag == "odoo"


def test_demo_products_use_odoo_19_product_type_field():
    tree = ElementTree.parse(ADDON_ROOT / "data" / "demo_products.xml")

    product_records = [
        node
        for node in tree.getroot().iter("record")
        if node.attrib.get("model") == "product.template"
    ]

    assert product_records
    for record in product_records:
        fields = {field.attrib["name"]: field.text for field in record.iter("field")}

        assert "detailed_type" not in fields
        assert fields["type"] == "service"


def test_access_control_rows_cover_custom_models_for_demo_users():
    access_path = ADDON_ROOT / "security" / "ir.model.access.csv"

    with access_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    rows_by_model = {row["model_id:id"]: row for row in rows}

    deal_context = rows_by_model["model_deal_agent_deal_context"]
    assert deal_context["group_id:id"] == "base.group_user"
    assert deal_context["perm_read"] == "1"
    assert deal_context["perm_write"] == "1"
    assert deal_context["perm_create"] == "1"

    audit_log = rows_by_model["model_deal_agent_audit_log"]
    assert audit_log["group_id:id"] == "base.group_user"
    assert audit_log["perm_read"] == "1"


def test_menu_items_expose_bridge_actions():
    menu_path = ADDON_ROOT / "views" / "deal_agent_menus.xml"
    tree = ElementTree.parse(menu_path)

    menus = {node.attrib["id"]: node.attrib for node in tree.getroot().iter("menuitem")}

    assert menus["menu_deal_agent_root"]["name"] == "Deal Agent"
    assert menus["menu_deal_agent_contexts"]["parent"] == "menu_deal_agent_root"
    assert menus["menu_deal_agent_contexts"]["action"] == "action_deal_agent_contexts"
    assert menus["menu_deal_agent_audit_logs"]["parent"] == "menu_deal_agent_root"
    assert menus["menu_deal_agent_audit_logs"]["action"] == "action_deal_agent_audit_logs"
