#!/usr/bin/env python3
"""Write the KiCad project file with the project-level design rules.

KiCad 10 stores minimum clearance, track width, via size and DRC severity
settings in the .kicad_pro file rather than in the .kicad_pcb file.  Keeping
this generator next to build_pcb.py makes the rules reproducible.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRO_PATH = ROOT / "VaultKey_USB.kicad_pro"

DEFAULTS = {
    "apply_defaults_to_fp_barcodes": False,
    "apply_defaults_to_fp_dimensions": False,
    "apply_defaults_to_fp_fields": False,
    "apply_defaults_to_fp_shapes": False,
    "apply_defaults_to_fp_text": False,
    "board_outline_line_width": 0.05,
    "copper_line_width": 0.2,
    "copper_text_italic": False,
    "copper_text_size_h": 1.5,
    "copper_text_size_v": 1.5,
    "copper_text_thickness": 0.3,
    "copper_text_upright": False,
    "courtyard_line_width": 0.05,
    "dimension_precision": 4,
    "dimension_units": 3,
    "fab_line_width": 0.1,
    "fab_text_italic": False,
    "fab_text_size_h": 1.0,
    "fab_text_size_v": 1.0,
    "fab_text_thickness": 0.15,
    "fab_text_upright": False,
    "other_line_width": 0.1,
    "other_text_italic": False,
    "other_text_size_h": 1.0,
    "other_text_size_v": 1.0,
    "other_text_thickness": 0.15,
    "other_text_upright": False,
    "pads": {"drill": 0.8, "height": 1.27, "width": 1.27},
    "silk_line_width": 0.1,
    "silk_text_italic": False,
    "silk_text_size_h": 1.0,
    "silk_text_size_v": 1.0,
    "silk_text_thickness": 0.1,
    "silk_text_upright": False,
    "zones": {
        "border_display_style": 2,
        "border_hatch_pitch": 0.5,
        "corner_radius": 0.0,
        "corner_smoothing": 0,
        "fill_mode": 0,
        "hatch_gap": 1.5,
        "hatch_orientation": 0.0,
        "hatch_smoothing_level": 0,
        "hatch_smoothing_value": 0.1,
        "hatch_thickness": 1.0,
        "min_clearance": 0.25,
        "min_island_area": 10.0,
        "min_thickness": 0.25,
        "pad_connection": 1,
        "remove_islands": 0,
        "thermal_relief_gap": 0.3,
        "thermal_relief_spoke_width": 0.5,
    },
}

RULES = {
    "max_error": 0.005,
    "min_clearance": 0.20,
    "min_connection": 0.0,
    "min_copper_edge_clearance": 0.50,
    "min_groove_width": 0.0,
    "min_hole_clearance": 0.25,
    "min_hole_to_hole": 0.25,
    "min_microvia_diameter": 0.30,
    "min_microvia_drill": 0.10,
    "min_resolved_spokes": 2,
    "min_silk_clearance": 0.0,
    "min_text_height": 0.8,
    "min_text_thickness": 0.08,
    "min_through_hole_diameter": 0.30,
    "min_track_width": 0.20,
    "min_via_annular_width": 0.15,
    "min_via_diameter": 0.60,
    "solder_mask_to_copper_clearance": 0.0,
    "use_height_for_length_calcs": True,
}

# Cosmetic silkscreen checks are disabled: the board itself is fully checked
# for copper, drill, courtyard and connectivity errors.  The display module
# intentionally covers the bottom-left mounting screw from above.
SEVERITIES = {
    "annular_width": "error",
    "clearance": "error",
    "connection_width": "warning",
    "copper_edge_clearance": "error",
    "copper_sliver": "warning",
    "courtyards_overlap": "error",
    "creepage": "error",
    "diff_pair_gap_out_of_range": "error",
    "diff_pair_uncoupled_length_too_long": "error",
    "drill_out_of_range": "error",
    "duplicate_footprints": "warning",
    "extra_footprint": "warning",
    "footprint": "error",
    "footprint_filters_mismatch": "ignore",
    "footprint_symbol_field_mismatch": "warning",
    "footprint_symbol_mismatch": "warning",
    "footprint_type_mismatch": "ignore",
    "hole_clearance": "error",
    "hole_to_hole": "warning",
    "holes_co_located": "warning",
    "invalid_outline": "error",
    "isolated_copper": "warning",
    "item_on_disabled_layer": "error",
    "items_not_allowed": "error",
    "length_out_of_range": "error",
    "lib_footprint_issues": "ignore",
    "lib_footprint_mismatch": "warning",
    "malformed_courtyard": "error",
    "microvia_drill_out_of_range": "error",
    "missing_courtyard": "ignore",
    "npth_inside_courtyard": "error",
    "pth_inside_courtyard": "error",
    "shorting_items": "error",
    "silk_edge_clearance": "ignore",
    "silk_over_copper": "ignore",
    "silk_overlap": "ignore",
    "skew_out_of_range": "error",
    "solder_mask_bridge": "error",
    "starved_thermal": "error",
    "text_height": "warning",
    "text_thickness": "warning",
    "through_hole_pad_without_hole": "error",
    "too_many_vias": "error",
    "track_dangling": "warning",
    "track_width": "error",
    "tuned_length_out_of_range": "error",
    "unconnected_items": "error",
    "via_dangling": "warning",
    "zone_has_empty_net": "error",
    "zones_intersect": "error",
}


def netclass(name: str, clearance: float, track: float, via_d: float,
             via_drill: float, diff_w: float, diff_gap: float) -> dict:
    return {
        "bus_width": 12,
        "clearance": clearance,
        "diff_pair_gap": diff_gap,
        "diff_pair_via_gap": 0.25,
        "diff_pair_width": diff_w,
        "line_style": 0,
        "microvia_diameter": 0.3,
        "microvia_drill": 0.1,
        "name": name,
        "pcb_color": "",
        "priority": 0,
        "schematic_color": "",
        "track_width": track,
        "via_diameter": via_d,
        "via_drill": via_drill,
        "wire_width": 6,
    }


def main() -> None:
    project = {
        "board": {
            "3dviewports": [],
            "design_settings": {
                "defaults": DEFAULTS,
                "diff_pair_dimensions": [],
                "drc_exclusions": [],
                "meta": {"version": 2},
                "rule_severities": SEVERITIES,
                "rules": RULES,
                "teardrop_options": [],
                "teardrop_parameters": [],
                "track_widths": [0.0, 0.2, 0.25, 0.5],
                "tuning_pattern_settings": {},
                "via_dimensions": [
                    {"diameter": 0.0, "drill": 0.0},
                    {"diameter": 0.6, "drill": 0.3},
                    {"diameter": 0.8, "drill": 0.4},
                ],
                "zones_allow_external_fillets": False,
            },
            "layer_presets": [],
            "viewports": [],
        },
        "boards": [],
        "cvpcb": {"equivalence_files": []},
        "erc": {
            "erc_exclusions": [],
            "meta": {"version": 0},
            "pin_map": [],
            "rule_severities": {},
            "severities": {},
        },
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": PRO_PATH.name, "version": 1},
        "net_settings": {
            "classes": [],
            "meta": {"version": 3},
            "net_colors": {},
            "netclass_patterns": [],
            "netclass_patterns_uv": [],
            "netclasses": {
                "Default": netclass("Default", 0.20, 0.25, 0.60, 0.30, 0.25, 0.20),
                "Power": netclass("Power", 0.25, 0.50, 0.80, 0.40, 0.25, 0.20),
            },
        },
        "pcbnew": {
            "last_paths": {
                "gencad": "",
                "idf": "",
                "netlist": "",
                "specctra_dsn": "fabrication/VaultKey_USB.dsn",
                "step": "",
                "vrml": "",
            },
            "page_layout_descr_file": "",
        },
        "schematic": {
            "legacy_lib_dir": "",
            "legacy_lib_list": [],
            "meta": {"version": 1},
            "net_format_name": "",
            "page_layout_descr_file": "",
            "plot_directory": "",
            "spice_current_sheet_as_root": False,
            "spice_external_command": "spice \"%I\"",
            "spice_model_current_sheet_as_root": True,
            "spice_save_all_currents": False,
            "spice_save_all_dissipations": False,
            "spice_save_all_voltages": False,
            "subpart_first_id": 65,
            "subpart_id_separator": 0,
        },
        "sheets": [["", ""]],
        "text_variables": {},
    }

    PRO_PATH.write_text(json.dumps(project, indent=2) + "\n")
    print(f"wrote {PRO_PATH}")


if __name__ == "__main__":
    main()
