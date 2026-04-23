"""CSV and Excel export utilities.

All output formatting lives here. Supports:
- Single city CSV export
- Multi-city comparison CSV
- Excel .xlsx export with formatted sheets
- Data structures ready for matplotlib plotting
"""
import pandas as pd
from pathlib import Path
from typing import List, Optional

from bau.config import OUTPUTS_DIR


def export_single_city_csv(
    df: pd.DataFrame,
    city_name: str,
    output_dir: Optional[str] = None,
) -> Path:
    """Export a single city's results to CSV.

    Args:
        df: DataFrame from City.run_all_years().
        city_name: City name for the filename.
        output_dir: Output directory. Defaults to outputs/csv/.

    Returns:
        Path to the written CSV file.
    """
    if output_dir is None:
        output_dir = OUTPUTS_DIR / "csv"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    fname = city_name.lower().replace(" ", "_").replace(".", "") + "_results.csv"
    filepath = output_dir / fname
    df.to_csv(filepath, index=False)
    return filepath


def export_multi_city_csv(
    dfs: List[pd.DataFrame],
    output_dir: Optional[str] = None,
    filename: str = "multi_city_comparison.csv",
) -> Path:
    """Export multiple cities' results to a single CSV.

    Cities are stacked vertically (long format) for easy filtering/plotting.

    Args:
        dfs: List of DataFrames from City.run_all_years(), one per city.
        output_dir: Output directory. Defaults to outputs/csv/.
        filename: Output filename.

    Returns:
        Path to the written CSV file.
    """
    if output_dir is None:
        output_dir = OUTPUTS_DIR / "csv"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    combined = pd.concat(dfs, ignore_index=True)
    filepath = output_dir / filename
    combined.to_csv(filepath, index=False)
    return filepath


def export_xlsx(
    dfs: List[pd.DataFrame],
    city_names: List[str],
    output_dir: Optional[str] = None,
    filename: str = "iam_results.xlsx",
) -> Path:
    """Export results to Excel with one sheet per city plus a summary sheet.

    Args:
        dfs: List of DataFrames from City.run_all_years().
        city_names: Corresponding city names for sheet naming.
        output_dir: Output directory. Defaults to outputs/xlsx/.
        filename: Output filename.

    Returns:
        Path to the written Excel file.
    """
    if output_dir is None:
        output_dir = OUTPUTS_DIR / "xlsx"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        # Summary sheet with all cities
        combined = pd.concat(dfs, ignore_index=True)
        combined.to_excel(writer, sheet_name="Summary", index=False)

        # Individual city sheets
        for name, df in zip(city_names, dfs):
            sheet_name = name[:31]  # Excel sheet name limit
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    return filepath


def prepare_plot_data(
    dfs: List[pd.DataFrame],
    metric: str = "total_savings_mtco2e",
) -> pd.DataFrame:
    """Prepare data for matplotlib plotting.

    Pivots the data so each city is a column, years are the index,
    and values are the specified metric.

    Args:
        dfs: List of DataFrames from City.run_all_years().
        metric: Column name to plot. Default is total savings.

    Returns:
        DataFrame with years as index and cities as columns.
    """
    combined = pd.concat(dfs, ignore_index=True)
    pivoted = combined.pivot(index="year", columns="city", values=metric)
    return pivoted
