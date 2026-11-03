"""Optional pinned upstream metadata validation, including reading catalog recordsets offline."""
import csv
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYSTOW_HOME", str(ROOT / "work/validator-cache"))

from farajamh.exports import validate_catalog, validate_sssom
from farajamh.pilot import deny_network


def validate(directory: Path):
    with deny_network():
        import mlcroissant as mlc
        import sssom_schema
        mapping_file = next(directory.glob("*.sssom.tsv"))
        profile = validate_sssom(mapping_file)
        rows = list(csv.DictReader(io.StringIO("\n".join(l for l in mapping_file.read_text().splitlines() if not l.startswith("#"))), delimiter="\t"))
        model = sssom_schema.MappingSet(**profile["metadata"], mappings=rows)
        validate_catalog(directory / "catalog.jsonld")
        dataset = mlc.Dataset(jsonld=str(directory / "catalog.jsonld"))
        counts = {rs.id: sum(1 for _ in dataset.records(record_set=rs.id)) for rs in dataset.metadata.record_sets}
        return {"sssom_schema": "1.0.0", "official_mapping_model_rows": len(model.mappings), "mlcroissant": "1.0.22",
            "recordset_counts": counts, "network_blocked": True}


if __name__ == "__main__":
    print(json.dumps(validate(Path(sys.argv[1]).resolve()), indent=2))
