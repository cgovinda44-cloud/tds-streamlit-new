import io
from datetime import datetime

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer


# ----------------------------
# App settings
# ----------------------------
st.set_page_config(page_title="TDS Working Generator", layout="wide")

SECTIONS = [
    "TDS on Compensation (194I)",
    "TDS on Commission (194H)",
    "TDS on Contractor (194C)",
    "TDS on Professional Fees (194J)",
]

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# Company Master (edit this list anytime)
company_master = pd.DataFrame({
    "Company": [
        "Malpani Infertility Clinic Pvt Ltd",
        "Community Health Research Programme Charitable Trust",
        "Frugality Ventures LLP",
        "Narayan Chandra Trust"
    ],
    "TAN": [
        "MUMM18859B",
        "MUMC12694D",
        "MUMF11570G",
        "MUMN07896A"
    ]
})


def safe_filename(s: str) -> str:
    keep = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-")
    cleaned = "".join([c for c in s if c in keep]).strip()
    return cleaned.replace(" ", "_")


def build_pdf_bytes(company: str, tan: str, month: str, year: str, df: pd.DataFrame) -> bytes:
    """
    Builds a tabular PDF with:
    - Yellow header row
    - Thick borders
    - Section-wise tables + totals
    """
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    title = f"TDS Payment for the month of {month} {year}"
    company_line = f"{company} ({tan})"

    elements.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    elements.append(Paragraph(f"<b>{company_line}</b>", styles["Normal"]))
    elements.append(Spacer(1, 12))

    # Preserve your standard section order, only print those present
    present_sections = [s for s in SECTIONS if s in df["Section"].unique()]

    for section in present_sections:
        sec_df = df[df["Section"] == section].copy()

        elements.append(Paragraph(f"<b>{section}</b>", styles["Heading3"]))
        elements.append(Spacer(1, 6))

        table_data = [["Date", "Party", "Gross", "%", "TDS"]]

        for _, r in sec_df.iterrows():
            table_data.append([
                str(r["Date"]),
                str(r["Party"]),
                f"{r['Gross']:,.0f}",
                f"{r['Rate']:.1f}",
                f"{r['TDS']:,.0f}",
            ])

        total_tds = sec_df["TDS"].sum()
        table_data.append(["", "", "", "TOTAL", f"{total_tds:,.0f}"])

        table = Table(table_data, colWidths=[85, 230, 80, 45, 80])

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.yellow),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),

            ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ("FONTNAME", (3, -1), (-1, -1), "Helvetica-Bold"),

            ("BOX", (0, 0), (-1, -1), 2.0, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 1.0, colors.black),

            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 16))

    grand_total = df["TDS"].sum()
    elements.append(Paragraph(f"<b>Grand Total TDS: {grand_total:,.0f}</b>", styles["Normal"]))

    doc.build(elements)
    return buffer.getvalue()


# ----------------------------
# Session State
# ----------------------------
if "entries" not in st.session_state:
    st.session_state.entries = []


# ----------------------------
# UI
# ----------------------------
st.title("TDS Working Generator")

with st.sidebar:
    st.header("Company & Period")

    company = st.selectbox("Company", company_master["Company"].tolist())
    tan = company_master.loc[company_master["Company"] == company, "TAN"].iloc[0]
    month = st.selectbox("Month", MONTHS, index=0)
    year = st.text_input("Year", value=str(datetime.now().year))

    st.caption(f"**TAN:** {tan}")

st.subheader(f"{company} ({tan}) — {month} {year}")

left, right = st.columns([1, 1.5])

with left:
    st.markdown("### Add Entry")
    with st.form("add_entry", clear_on_submit=True):
        section = st.selectbox("TDS Section", SECTIONS)
        date_str = st.text_input("Date (DD-MM-YYYY)", value=datetime.now().strftime("%d-%m-%Y"))
        party = st.text_input("Party Name")
        gross = st.number_input("Gross Amount", min_value=0.0, step=1000.0, format="%.2f")
        rate = st.number_input("TDS %", min_value=0.0, step=0.5, format="%.2f")

        add = st.form_submit_button("Add Row")

        if add:
            if not party.strip():
                st.error("Party Name is required.")
            else:
                tds_amt = round(gross * rate / 100.0, 2)
                st.session_state.entries.append({
                    "Date": date_str.strip(),
                    "Section": section,
                    "Party": party.strip(),
                    "Gross": float(gross),
                    "Rate": float(rate),
                    "TDS": float(tds_amt),
                })
                st.success(f"Added. TDS = {tds_amt:,.2f}")

with right:
    st.markdown("### Entries")
    if st.session_state.entries:
        df = pd.DataFrame(st.session_state.entries)

        st.dataframe(df[["Date","Section","Party","Gross","Rate","TDS"]], use_container_width=True, hide_index=True)

        st.markdown("### Section Totals")
        totals = df.groupby("Section")[["Gross","TDS"]].sum().reset_index()
        st.dataframe(totals, use_container_width=True, hide_index=True)

        st.markdown(f"**Grand Total TDS:** {df['TDS'].sum():,.2f}")

        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            if st.button("Remove Last Row"):
                st.session_state.entries.pop()
                st.rerun()

        with c2:
            if st.button("Clear All"):
                st.session_state.entries = []
                st.rerun()

        pdf_bytes = build_pdf_bytes(company, tan, month, year, df)
        pdf_name = f"TDS_{safe_filename(company)}_{month}_{year}.pdf"

        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=pdf_name,
            mime="application/pdf"
        )
    else:
        st.info("No entries yet. Add entries from the left.")
