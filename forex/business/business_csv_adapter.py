"""
business_csv_adapter.py — Normalize business CSV/Excel exports to ASTRA's internal schema.

Supported formats (auto-detected from column names):
  - Sales report       : date, revenue/sales/ventas, cost/costo, product/producto
  - Expense report     : date, amount/monto, category/categoria, description
  - Cash flow          : date, inflow/ingreso, outflow/egreso, balance/saldo
  - Inventory          : date, product, units/unidades, unit_cost/costo_unitario
  - Combined P&L       : date, revenue, cost_of_sales, gross_margin, expenses, net_income

Internal schema after normalization:
  date, period, revenue, cost_of_sales, gross_profit, expenses,
  net_income, units_sold, unit_cost, category, product, balance
  (missing columns are filled with NaN)
"""

import os
import pandas as pd
import numpy as np
from typing import Optional


# ── Column name synonyms ────────────────────────────────────────────────────
_SYNONYMS = {
    "date": [
        "date", "fecha", "periodo", "period", "month", "mes",
        "week", "semana", "day", "dia", "timestamp", "time",
    ],
    "revenue": [
        "revenue", "ventas", "sales", "ingresos", "income",
        "total_sales", "total_ventas", "net_sales", "gross_sales",
        "facturacion", "billing",
    ],
    "cost_of_sales": [
        "cost_of_sales", "costo_ventas", "cogs", "cost_of_goods_sold",
        "costos", "costo", "cost", "costo_de_venta",
    ],
    "gross_profit": [
        "gross_profit", "utilidad_bruta", "margen_bruto", "gross_margin",
        "ganancia_bruta",
    ],
    "expenses": [
        "expenses", "gastos", "operating_expenses", "opex",
        "gastos_operacionales", "costos_fijos", "overhead",
    ],
    "net_income": [
        "net_income", "utilidad_neta", "net_profit", "ganancia_neta",
        "resultado", "bottom_line", "profit", "beneficio",
    ],
    "units_sold": [
        "units_sold", "unidades_vendidas", "quantity", "cantidad",
        "units", "unidades", "qty",
    ],
    "unit_cost": [
        "unit_cost", "costo_unitario", "precio_costo", "cost_per_unit",
    ],
    "category": [
        "category", "categoria", "segment", "segmento", "type", "tipo",
        "department", "departamento", "area",
    ],
    "product": [
        "product", "producto", "item", "sku", "service", "servicio",
        "description", "descripcion",
    ],
    "balance": [
        "balance", "saldo", "cash", "caja", "cash_balance",
        "saldo_final", "net_cash",
    ],
    "inflow": [
        "inflow", "ingreso", "cash_in", "entrada", "receipts", "cobros",
    ],
    "outflow": [
        "outflow", "egreso", "cash_out", "salida", "payments", "pagos",
    ],
}

_BUSINESS_TYPES = {
    "sales":     ["revenue", "cost_of_sales", "units_sold"],
    "expenses":  ["expenses", "category"],
    "cashflow":  ["inflow", "outflow", "balance"],
    "inventory": ["units_sold", "unit_cost", "product"],
    "pl":        ["revenue", "gross_profit", "net_income"],
}


def detect_business_type(df: pd.DataFrame) -> str:
    """Infer the type of business report from column names."""
    cols = set(df.columns.str.lower())
    scores = {}
    for btype, required in _BUSINESS_TYPES.items():
        scores[btype] = sum(1 for c in required if c in cols)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "generic"


def adapt_business_csv(
    filepath: str,
    business_type: Optional[str] = None,
    date_col: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load a business CSV/Excel and normalize it to the internal ASTRA schema.

    Parameters
    ----------
    filepath      : path to the CSV or Excel file
    business_type : optional override ('sales', 'expenses', 'cashflow',
                    'inventory', 'pl', 'generic')
    date_col      : optional override for the date column name

    Returns
    -------
    pd.DataFrame with normalized columns and a parsed 'date' index.
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(filepath)
    else:
        df = pd.read_csv(filepath, low_memory=False)

    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # ── Resolve column synonyms ───────────────────────────────────────────
    rename_map = {}
    used_targets = set()
    for target, synonyms in _SYNONYMS.items():
        if target in used_targets:
            continue
        for syn in synonyms:
            if syn in df.columns and target not in df.columns:
                rename_map[syn] = target
                used_targets.add(target)
                break

    df.rename(columns=rename_map, inplace=True)

    # ── Parse date ────────────────────────────────────────────────────────
    if date_col and date_col in df.columns:
        df.rename(columns={date_col: "date"}, inplace=True)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df.dropna(subset=["date"], inplace=True)
        df.sort_values("date", inplace=True)
        df.reset_index(drop=True, inplace=True)
        df["period"] = df["date"].dt.to_period("M").astype(str)
    else:
        df["date"]   = pd.NaT
        df["period"] = "unknown"

    # ── Derive missing financial columns ─────────────────────────────────
    if "gross_profit" not in df.columns:
        if "revenue" in df.columns and "cost_of_sales" in df.columns:
            df["gross_profit"] = df["revenue"] - df["cost_of_sales"]

    if "net_income" not in df.columns:
        if "gross_profit" in df.columns and "expenses" in df.columns:
            df["net_income"] = df["gross_profit"] - df["expenses"]

    if "balance" not in df.columns:
        if "inflow" in df.columns and "outflow" in df.columns:
            df["balance"] = df["inflow"] - df["outflow"]

    # ── Auto-detect type ──────────────────────────────────────────────────
    if business_type is None:
        business_type = detect_business_type(df)
    df.attrs["business_type"] = business_type

    # ── Drop fully-empty rows ─────────────────────────────────────────────
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        df.dropna(subset=numeric_cols, how="all", inplace=True)

    df.reset_index(drop=True, inplace=True)
    return df


def check_business_compatibility(filepath: str) -> dict:
    """
    Preview what the adapter will do without actually running the pipeline.
    Returns a dict with detected type, column mappings, and row count.
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xlsx", ".xls"):
        raw = pd.read_excel(filepath, nrows=5)
    else:
        raw = pd.read_csv(filepath, nrows=5)

    raw.columns = raw.columns.str.strip().str.lower().str.replace(" ", "_")

    rename_map = {}
    for target, synonyms in _SYNONYMS.items():
        for syn in synonyms:
            if syn in raw.columns and target not in raw.columns:
                rename_map[syn] = target
                break

    try:
        total_rows = sum(1 for _ in open(filepath)) - 1
    except Exception:
        total_rows = "unknown"

    detected_type = detect_business_type(raw.rename(columns=rename_map))

    return {
        "compatible":        True,
        "detected_type":     detected_type,
        "will_be_renamed":   rename_map,
        "original_columns":  list(raw.columns),
        "estimated_rows":    total_rows,
    }
