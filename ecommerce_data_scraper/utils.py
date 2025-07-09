from typing import List, Dict, Optional
import pandas as pd
from agents.listing_summarizer_agent import Variant


def process_variants(
    row: pd.Series, variants_list: Optional[List[Variant]]
) -> pd.DataFrame:
    """
    Transforms a list of scraped product variants into a structured DataFrame.

    This function takes the original product row and a list of variants (if any)
    and generates a new DataFrame containing:
    1. A "parent" row: This row represents the main product. If there are multiple
       variants, it aggregates the attribute values (e.g., "Red,Blue,Green").
       If there's only one variant or no variants, it's a "simple" product row.
    2. "Child" rows: If there are multiple variants, child rows are created for
       each one. Each child row represents a specific variant and is linked to
       the parent row.
    """
    # If no variants were scraped, return the original row as is.
    if not variants_list:
        return pd.DataFrame([row])

    # Extract technical specifications from each variant into a list of dictionaries.
    all_child_data: List[Dict[str, str]] = []
    for scraped_variant in variants_list:
        scraped_specs = {
            spec.name: spec.value for spec in scraped_variant.technical_specifications
        }
        all_child_data.append(scraped_specs)

    if not all_child_data:
        return pd.DataFrame([row])

    # --- Parent Row Generation ---
    # This section creates the main "variable" product row that summarizes all variants.
    parent_attributes: Dict[str, str] = {}
    all_attribute_names = sorted(list(all_child_data[0].keys()))

    for name in all_attribute_names:
        # Collect all unique values for the current attribute across all variants.
        values = {child.get(name) for child in all_child_data}
        values = {v for v in values if v is not None and v != ""}

        if len(values) > 1:
            # If there are multiple values, they are combined into a single string.
            parent_attributes[name] = ",".join(sorted(list(values)))
        elif len(values) == 1:
            # If there is only one unique value, it is used directly.
            parent_attributes[name] = values.pop()

    parent_row = row.copy()
    parent_row["Type"] = "variable" if len(all_child_data) > 1 else "simple"

    # Clear any pre-existing attribute columns from the original row.
    for col in parent_row.index:
        if isinstance(col, str) and col.startswith("Attribute "):
            parent_row[col] = None

    # Populate the parent row with the new, aggregated attributes.
    for i, name in enumerate(all_attribute_names):
        col_idx = i + 1
        parent_row[f"Attribute {col_idx} name"] = name
        parent_row[f"Attribute {col_idx} value(s)"] = parent_attributes.get(name, "")

    # --- Child Row Generation ---
    # This section creates individual rows for each variant if the product is "variable".
    child_rows_data = []
    if parent_row["Type"] == "variable":
        for child_data in all_child_data:
            child_row = parent_row.copy()
            child_row["ID"] = ""  # Child rows have no ID.
            child_row["Parent"] = f"id:{parent_row['ID']}"
            child_row["Type"] = "variation"
            child_row["url"] = ""  # URL is only on the parent.

            # Populate the child row with its specific attribute values.
            for i, attr_name in enumerate(all_attribute_names):
                col_idx = i + 1
                parent_value = parent_attributes.get(attr_name, "")
                # Only varying attributes are set on child rows.
                if "," in str(parent_value):
                    child_row[f"Attribute {col_idx} name"] = attr_name
                    child_row[f"Attribute {col_idx} value(s)"] = child_data.get(
                        attr_name, ""
                    )
                else:
                    # Static attributes are cleared on child rows to avoid redundancy.
                    child_row[f"Attribute {col_idx} name"] = None
                    child_row[f"Attribute {col_idx} value(s)"] = None

            child_rows_data.append(child_row)

    # Combine the parent row and all child rows into a single DataFrame.
    return pd.concat(
        [pd.DataFrame([parent_row]), pd.DataFrame(child_rows_data)], ignore_index=True
    )


def find_start_attribute_col(row: pd.Series) -> int:
    """
    Finds the next available attribute column index for a given row.
    This is used for logging errors into the attribute columns.
    """
    # Find all existing "Attribute X name" columns and determine the highest index.
    existing_attrs = [
        int(c.split(" ")[1])
        for c in row.index
        if isinstance(c, str) and c.startswith("Attribute ") and " name" in c
    ]
    max_attr = max(existing_attrs) if existing_attrs else 0
    return max_attr + 1
