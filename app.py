from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DATA_FIL = Path(__file__).parent / "graddage_aalborg.csv"
MÅNEDER_KORT = ["jan", "feb", "mar", "apr", "maj", "jun",
                "jul", "aug", "sep", "okt", "nov", "dec"]
# Tydeligt adskilte farver (orange, blå, grøn, magenta, gul, lilla, brun) – virker i både light og dark mode
ÅR_FARVER = ["#FF9F1C", "#3A86FF", "#06D6A0", "#F72585", "#FFD60A", "#8338EC", "#A98467"]
KILDE_TIDLIGERE = "https://aalborgforsyning.dk/hverdag-med-forsyning/graddagetal-vejrpaavirkning/tidligere-aars-graddagetal/"
KILDE_2026 = "https://aalborgforsyning.dk/hverdag-med-forsyning/graddagetal-vejrpaavirkning/#graddage%202025"
KILDE_TEKST = (
    "**Kilde:** Aalborg Forsyning  \n"
    f"2023–2025: [Tidligere års graddagetal]({KILDE_TIDLIGERE})  \n"
    f"2026: [Graddagetal og vejrpåvirkning]({KILDE_2026})"
)
PÅKRÆVET = {"År", "Måned nr", "Antal graddage", "Normal"}

st.set_page_config(page_title="Graddage – Aalborg Forsyning", layout="wide")


def forbered(df: pd.DataFrame) -> pd.DataFrame:
    mangler = PÅKRÆVET - set(df.columns)
    if mangler:
        st.error(f"Filen mangler kolonnerne: {', '.join(sorted(mangler))}")
        st.stop()
    df = df.copy()
    df["Dato"] = pd.to_datetime(dict(year=df["År"], month=df["Måned nr"], day=1))
    df = df.sort_values("Dato").reset_index(drop=True)
    df["Måned"] = df["Dato"].dt.month.map(lambda m: MÅNEDER_KORT[m - 1]) + " " + df["År"].astype(str)
    df["Afvigelse"] = df["Normal"] - df["Antal graddage"]  # plus = færre graddage end normalen
    df["Afvigelse %"] = (df["Afvigelse"] / df["Normal"] * 100).round(1)
    return df


def tegn(x, decimaler: int = 0) -> str:
    """Formaterer med fortegn: +5, -5 eller 0."""
    if pd.isna(x):
        return ""
    if round(x, decimaler) == 0:
        return "0"
    return f"{x:+.{decimaler}f}"


def normal_farve() -> str:
    """Lys linje i dark mode, mørk i light mode. Neutral grå hvis temaet ikke kan aflæses."""
    try:
        return "#ffffff" if st.context.theme.type == "dark" else "#222222"
    except Exception:
        return "#9e9e9e"


@st.cache_data
def hent_standarddata(filversion: float) -> pd.DataFrame:
    # filversion (filens ændringstidspunkt) gør, at cachen ugyldiggøres, når CSV'en ændres
    return forbered(pd.read_csv(DATA_FIL, sep=";", encoding="utf-8-sig"))


# ---------- Sidebar ----------
st.sidebar.header("Indstillinger")
df = hent_standarddata(DATA_FIL.stat().st_mtime)

etiketter = df["Måned"].tolist()
start, slut = st.sidebar.select_slider(
    "Periode", options=etiketter, value=(etiketter[0], etiketter[-1]),
    help="Træk i håndtagene for at vælge fra- og til-måned (begge inklusive).",
)
i0, i1 = etiketter.index(start), etiketter.index(slut)
udsnit = df.iloc[i0 : i1 + 1]

st.sidebar.divider()
st.sidebar.download_button(
    "⬇️ Download hele datasættet (CSV)",
    DATA_FIL.read_bytes(),
    file_name="graddage_aalborg.csv",
    mime="text/csv",
    help="Alle måneder og år, semikolon-separeret (åbner direkte i dansk Excel).",
)
st.sidebar.markdown(KILDE_TEKST)

# ---------- Hoved ----------
st.title("Graddage – Aalborg Forsyning")
st.caption(f"Valgt periode: **{start}** til **{slut}** ({len(udsnit)} måneder)")

samlet, normal = udsnit["Antal graddage"].sum(), udsnit["Normal"].sum()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Graddage i alt", f"{samlet:,}".replace(",", "."))
k2.metric("Normal i alt", f"{normal:,}".replace(",", "."))
k3.metric("Afvigelse", f"{normal - samlet:+,}".replace(",", "."), help="Normal minus faktisk. Plus = færre graddage end normalen, minus = flere.")
k4.metric("Afvigelse i %", f"{(normal - samlet) / normal * 100:+.1f} %", help="Plus = færre graddage end normalen, minus = flere.")

tab_graf, tab_år, tab_sam, tab_afv, tab_tabel, tab_priser = st.tabs(
    ["Graddage vs. normal", "År side om side", "Sammenlign og udtræk", "Afvigelse", "Tabel", "Prisudvikling"]
)
rækkefølge = udsnit["Måned"].tolist()

with tab_graf:
    basis = alt.Chart(udsnit).encode(x=alt.X("Måned:N", sort=rækkefølge, title=None))
    søjler = basis.mark_bar(opacity=0.85).encode(
        y=alt.Y("Antal graddage:Q", title="Graddage"),
        tooltip=["Måned", "Antal graddage", "Normal", alt.Tooltip("Afvigelse:Q", format="+d")],
    )
    linje = basis.mark_line(color="red", point=True).encode(y="Normal:Q")
    st.altair_chart((søjler + linje).properties(height=380), use_container_width=True)
    st.caption("Søjler: faktiske graddage. Rød linje: normal.")

with tab_år:
    NORMAL_FARVE = normal_farve()
    st.caption("Sammenligner kalenderår måned for måned. Bruger alle data, uafhængigt af periodevælgeren.")
    alle_år = sorted(df["År"].unique().tolist())
    valgte_år = st.multiselect("Vælg år", alle_år, default=alle_år)
    if not valgte_år:
        st.info("Vælg mindst ét år.")
    else:
        år_df = df[df["År"].isin(valgte_år)].copy()
        år_df["Kumulativ"] = år_df.groupby("År")["Antal graddage"].cumsum()
        år_df["Md"] = år_df["Måned nr"].map(lambda m: MÅNEDER_KORT[m - 1])
        år_df["År"] = år_df["År"].astype(str)

        normal_df = df.drop_duplicates("Måned nr").sort_values("Måned nr")[["Måned nr", "Normal"]].copy()
        normal_df["Md"] = normal_df["Måned nr"].map(lambda m: MÅNEDER_KORT[m - 1])
        normal_df["Kumulativ normal"] = normal_df["Normal"].cumsum()

        x = alt.X("Md:N", sort=MÅNEDER_KORT, title=None)
        normal_df["År"] = "Normal"

        # Fast farve pr. år (og for normalen), uanset hvilke år der er valgt.
        # Normalen er med i farveskalaen, så den får en prik i signaturen til højre.
        farve = alt.Color(
            "År:N", title=None,
            scale=alt.Scale(
                domain=[str(å) for å in alle_år] + ["Normal"],
                range=ÅR_FARVER[: len(alle_år)] + [NORMAL_FARVE],
            ),
            legend=alt.Legend(orient="right", symbolType="circle", symbolSize=140),
        )

        st.subheader("Graddage pr. måned")
        linjer = alt.Chart(år_df).mark_line(point=alt.OverlayMarkDef(size=70), strokeWidth=3).encode(
            x=x, y=alt.Y("Antal graddage:Q", title="Graddage"), color=farve,
            tooltip=["År", "Md", "Antal graddage", "Normal"],
        )
        norm = alt.Chart(normal_df).mark_line(strokeDash=[6, 4], strokeWidth=2).encode(
            color=farve, x=x, y="Normal:Q", tooltip=["Md", "Normal"],
        )
        st.altair_chart((linjer + norm).properties(height=350), use_container_width=True)
        st.caption("Stiplet linje: normal (prik i signaturen til højre).")

        st.subheader("Akkumuleret gennem året")
        kum = alt.Chart(år_df).mark_line(point=alt.OverlayMarkDef(size=70), strokeWidth=3).encode(
            x=x, y=alt.Y("Kumulativ:Q", title="Graddage (akkumuleret)"), color=farve,
            tooltip=["År", "Md", "Kumulativ"],
        )
        kum_norm = alt.Chart(normal_df).mark_line(strokeDash=[6, 4], strokeWidth=2).encode(
            color=farve, x=x, y="Kumulativ normal:Q", tooltip=["Md", "Kumulativ normal"],
        )
        st.altair_chart((kum + kum_norm).properties(height=350), use_container_width=True)
        st.caption("Viser, hvordan hvert år hober sig op i forhold til normalen. "
                   "Et år med manglende måneder (fx 2026) stopper ved sidste kendte måned.")

with tab_sam:
    st.caption("Justerbar sammenligning: vælg år, måneder og referencepunkt, og hent tallene ud som CSV.")
    ALLE_ÅR = sorted(df["År"].unique().tolist())
    FARVE_NORMAL = normal_farve()

    c1, c2 = st.columns([2, 1])
    valgte = c1.multiselect("År der vises", ALLE_ÅR, default=ALLE_ÅR, key="sam_år")
    baseline = c2.selectbox("Sammenlign mod", ["Normal"] + [str(å) for å in ALLE_ÅR], key="sam_ref")
    m0, m1 = st.select_slider("Måneder (fra – til)", options=MÅNEDER_KORT, value=("jan", "dec"), key="sam_md")
    c3, c4 = st.columns(2)
    akk = c3.radio("Visning", ["Måned for måned", "Akkumuleret"], horizontal=True, key="sam_akk") == "Akkumuleret"
    pct = c4.radio("Forskel angives i", ["Graddage", "Procent"], horizontal=True, key="sam_pct") == "Procent"

    mnd = list(range(MÅNEDER_KORT.index(m0) + 1, MÅNEDER_KORT.index(m1) + 2))
    kolonner = [str(å) for å in valgte]
    sammenlign = [k for k in kolonner if k != baseline]

    bred = df.pivot(index="Måned nr", columns="År", values="Antal graddage").reindex(mnd)
    bred.columns = [str(k) for k in bred.columns]
    bred["Normal"] = df.drop_duplicates("Måned nr").set_index("Måned nr")["Normal"].reindex(mnd)
    ref = bred[baseline]
    md_navn = lambda m: MÅNEDER_KORT[m - 1]

    if not kolonner:
        st.info("Vælg mindst ét år.")
    else:
        skala = alt.Scale(
            domain=[str(å) for å in ALLE_ÅR] + ["Normal"],
            range=ÅR_FARVER[: len(ALLE_ÅR)] + [FARVE_NORMAL],
        )
        farve = alt.Color("År:N", title=None, scale=skala,
                          legend=alt.Legend(orient="right", symbolType="circle", symbolSize=140))
        xs = alt.X("Md:N", sort=MÅNEDER_KORT, title=None)

        def til_lang(wide: pd.DataFrame, navn: str) -> pd.DataFrame:
            l = wide.copy()
            l["Md"] = [md_navn(m) for m in l.index]
            return l.melt(id_vars="Md", var_name="År", value_name=navn).dropna(subset=[navn])

        # --- Graf 1: graddage ---
        abs_bred = bred[kolonner + ["Normal"]]
        if akk:
            abs_bred = abs_bred.cumsum()
        abs_lang = til_lang(abs_bred, "Værdi")
        ytitel = "Graddage (akkumuleret)" if akk else "Graddage"
        st.subheader("Graddage")
        g_år = alt.Chart(abs_lang[abs_lang["År"] != "Normal"]).mark_line(
            point=alt.OverlayMarkDef(size=70), strokeWidth=3).encode(
            x=xs, y=alt.Y("Værdi:Q", title=ytitel), color=farve, tooltip=["År", "Md", "Værdi"])
        g_norm = alt.Chart(abs_lang[abs_lang["År"] == "Normal"]).mark_line(
            strokeDash=[6, 4], strokeWidth=2).encode(x=xs, y="Værdi:Q", color=farve, tooltip=["Md", "Værdi"])
        st.altair_chart((g_år + g_norm).properties(height=320), use_container_width=True)

        # --- Forskel mod reference (kun måneder hvor begge har data) ---
        def forskel(kol: str) -> pd.Series:
            begge = bred[kol].notna() & ref.notna()
            a, r = bred[kol].where(begge), ref.where(begge)
            d = r - a  # plus = færre graddage end referencen
            if akk:
                d, r = d.cumsum(), r.cumsum()
            return d / r * 100 if pct else d

        st.subheader(f"Forskel mod {baseline}")
        if not sammenlign:
            st.info("Vælg mindst ét andet år end referencen for at se forskellen.")
        else:
            f_bred = pd.DataFrame({k: forskel(k) for k in sammenlign})
            enhed = "%" if pct else "graddage"
            f_lang = til_lang(f_bred, "Forskel")
            nul = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(strokeDash=[4, 4], color=FARVE_NORMAL).encode(y="y:Q")
            f_linjer = alt.Chart(f_lang).mark_line(point=alt.OverlayMarkDef(size=70), strokeWidth=3).encode(
                x=xs, y=alt.Y("Forskel:Q", axis=alt.Axis(format="+.0f"),
                              title=f"Forskel ({enhed}{', akkumuleret' if akk else ''})"),
                color=farve, tooltip=["År", "Md", alt.Tooltip("Forskel:Q", format="+.1f")])
            st.altair_chart((nul + f_linjer).properties(height=320), use_container_width=True)
            st.caption(f"Forskel = {baseline} minus valgt år. Plus (+) = færre graddage end {baseline} (varmere). "
                       "Minus (-) = flere graddage (koldere). "
                       "Kun måneder hvor begge har data indgår.")

            # --- Sammenfatning ---
            rækker = []
            for k in sammenlign:
                begge = bred[k].notna() & ref.notna()
                if not begge.any():
                    continue
                a, r = bred.loc[begge, k], ref[begge]
                d = r - a
                m_max = d.abs().idxmax()
                rækker.append({
                    "År": k, "Graddage": int(a.sum()), f"Reference ({baseline})": int(r.sum()),
                    "Forskel": int(d.sum()), "Forskel %": round(d.sum() / r.sum() * 100, 1),
                    "Måneder sammenlignet": int(begge.sum()),
                    "Største månedsafvigelse": f"{md_navn(m_max)} ({d[m_max]:+.0f})",
                })
            st.subheader("Sammenfatning")
            oversigt = pd.DataFrame(rækker)
            oversigt_vis = oversigt.copy()
            if not oversigt.empty:
                oversigt_vis["Forskel"] = oversigt["Forskel"].map(tegn)
                oversigt_vis["Forskel %"] = oversigt["Forskel %"].map(lambda v: tegn(v, 1))
            st.dataframe(oversigt_vis, use_container_width=True, hide_index=True)

            st.subheader("Månedlige tal")
            maaned_tabel = bred[kolonner + ["Normal"]].copy()
            maaned_tabel.index = [md_navn(m) for m in maaned_tabel.index]
            maaned_tabel.index.name = "Måned"
            forskel_tabel = f_bred.copy()
            forskel_tabel.index = maaned_tabel.index
            forskel_tabel = forskel_tabel.round(1)
            t1, t2 = st.columns(2)
            t1.caption("Graddage pr. måned")
            t1.dataframe(maaned_tabel, use_container_width=True)
            t2.caption(f"Forskel mod {baseline} ({enhed}{', akkumuleret' if akk else ''})")
            t2.dataframe(
                forskel_tabel.apply(lambda kol: kol.map(lambda v: tegn(v, 1 if pct else 0))),
                use_container_width=True,
            )

            d1, d2, d3 = st.columns(3)
            csv = lambda x, idx: x.to_csv(index=idx, sep=";", decimal=",").encode("utf-8-sig")
            d1.download_button("⬇️ Sammenfatning", csv(oversigt, False), "sammenfatning.csv", "text/csv")
            d2.download_button("⬇️ Månedlige graddage", csv(maaned_tabel, True), "maanedlige_graddage.csv", "text/csv")
            d3.download_button("⬇️ Forskelle", csv(forskel_tabel, True), "forskelle.csv", "text/csv")

with tab_afv:
    afv = alt.Chart(udsnit).mark_bar().encode(
        x=alt.X("Måned:N", sort=rækkefølge, title=None),
        y=alt.Y("Afvigelse:Q", title="Afvigelse (normal − faktisk)", axis=alt.Axis(format="+.0f")),
        color=alt.condition(alt.datum.Afvigelse > 0, alt.value("#1f77b4"), alt.value("#d62728")),
        tooltip=["Måned", alt.Tooltip("Afvigelse:Q", format="+d"), alt.Tooltip("Afvigelse %:Q", format="+.1f")],
    )
    st.altair_chart(afv.properties(height=380), use_container_width=True)
    st.caption("Afvigelse = normal minus faktisk. Blå / plus (+) = færre graddage end normalen (varmere). Rød / minus (-) = flere graddage (koldere).")

with tab_tabel:
    vis = udsnit[["Måned", "Antal graddage", "Normal", "Afvigelse", "Afvigelse %"]]
    vis_vist = vis.copy()
    vis_vist["Afvigelse"] = vis["Afvigelse"].map(tegn)
    vis_vist["Afvigelse %"] = vis["Afvigelse %"].map(lambda v: tegn(v, 1))
    st.dataframe(vis_vist, use_container_width=True, hide_index=True)
    st.caption("Afvigelse = normal minus faktisk. Plus (+) = færre graddage end normalen, minus (-) = flere.")
    st.download_button(
        "⬇️ Download udsnit som CSV",
        vis.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="graddage_udsnit.csv",
        mime="text/csv",
    )

with tab_priser:
    st.subheader("Prisudvikling – Aalborg Forsyning")
    st.caption("Prisudvikling i fjernvarme over tid (inkl. moms). Kilder: [Aalborg Forsyning Priser](https://aalborgforsyning.dk/priser/) & [Artikelliste](https://aalborgforsyning.dk/artikelliste/)")

    pris_data = [
        {"Periode": "Indtil 1. dec 2022", "Pris pr. kWh (kr.)": 0.456, "Pris pr. MWh (kr.)": 456},
        {"Periode": "1. dec 2022 – 31. aug 2023", "Pris pr. kWh (kr.)": 0.547, "Pris pr. MWh (kr.)": 547},
        {"Periode": "1. sep 2023 – 31. mar 2024", "Pris pr. kWh (kr.)": 0.684, "Pris pr. MWh (kr.)": 684},
        {"Periode": "1. apr 2024 – 31. dec 2025", "Pris pr. kWh (kr.)": 0.821, "Pris pr. MWh (kr.)": 821},
        {"Periode": "1. jan 2026 – nuværende", "Pris pr. kWh (kr.)": 0.993, "Pris pr. MWh (kr.)": 993},
    ]
    df_priser = pd.DataFrame(pris_data)

    # Beregn ændringer i forhold til forrige periode
    df_priser["Stigning (kr.)"] = df_priser["Pris pr. kWh (kr.)"].diff().round(3)
    df_priser["Stigning (%)"] = (df_priser["Pris pr. kWh (kr.)"].pct_change() * 100).round(1)

    # Formater visning med fortegn (+ / -)
    df_priser_vis = df_priser.copy()
    df_priser_vis["Stigning (kr.)"] = df_priser_vis["Stigning (kr.)"].map(lambda x: f"{x:+.3f} kr." if pd.notna(x) else "-")
    df_priser_vis["Stigning (%)"] = df_priser_vis["Stigning (%)"].map(lambda x: f"{x:+.1f} %" if pd.notna(x) else "-")
    df_priser_vis["Pris pr. kWh (kr.)"] = df_priser_vis["Pris pr. kWh (kr.)"].map(lambda x: f"{x:.3f} kr.")
    df_priser_vis["Pris pr. MWh (kr.)"] = df_priser_vis["Pris pr. MWh (kr.)"].map(lambda x: f"{x:.0f} kr.")

    # Vis oversigtstabel
    st.dataframe(df_priser_vis, use_container_width=True, hide_index=True)

st.divider()
st.caption(KILDE_TEKST)
