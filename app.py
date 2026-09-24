from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DATA_FIL = Path(__file__).parent / "graddage_aalborg.csv"
MÅNEDER_KORT = ["jan", "feb", "mar", "apr", "maj", "jun",
                "jul", "aug", "sep", "okt", "nov", "dec"]
PÅKRÆVET = {"År", "Måned nr", "Antal graddage", "Normal"}

st.set_page_config(page_title="Graddage – Aalborg Forsyning", page_icon="🌡️", layout="wide")


def forbered(df: pd.DataFrame) -> pd.DataFrame:
    mangler = PÅKRÆVET - set(df.columns)
    if mangler:
        st.error(f"Filen mangler kolonnerne: {', '.join(sorted(mangler))}")
        st.stop()
    df = df.copy()
    df["Dato"] = pd.to_datetime(dict(year=df["År"], month=df["Måned nr"], day=1))
    df = df.sort_values("Dato").reset_index(drop=True)
    df["Måned"] = df["Dato"].dt.month.map(lambda m: MÅNEDER_KORT[m - 1]) + " " + df["År"].astype(str)
    df["Afvigelse"] = df["Antal graddage"] - df["Normal"]
    df["Afvigelse %"] = (df["Afvigelse"] / df["Normal"] * 100).round(1)
    return df


@st.cache_data
def hent_standarddata(filversion: float) -> pd.DataFrame:
    # filversion (filens ændringstidspunkt) gør, at cachen ugyldiggøres, når CSV'en ændres
    return forbered(pd.read_csv(DATA_FIL, sep=";", encoding="utf-8-sig"))


# ---------- Sidebar ----------
st.sidebar.header("Indstillinger")
upload = st.sidebar.file_uploader(
    "Brug egen CSV (valgfrit)", type="csv",
    help="Samme format som graddage_aalborg.csv (semikolon-separeret). Praktisk hvis du tilføjer 2026.",
)
if upload:
    df = forbered(pd.read_csv(upload, sep=";", encoding="utf-8-sig"))
else:
    df = hent_standarddata(DATA_FIL.stat().st_mtime)

etiketter = df["Måned"].tolist()
start, slut = st.sidebar.select_slider(
    "Periode", options=etiketter, value=(etiketter[0], etiketter[-1]),
    help="Træk i håndtagene for at vælge fra- og til-måned (begge inklusive).",
)
i0, i1 = etiketter.index(start), etiketter.index(slut)
udsnit = df.iloc[i0 : i1 + 1]

# ---------- Hoved ----------
st.title("🌡️ Graddage – Aalborg Forsyning")
st.caption(f"Valgt periode: **{start}** til **{slut}** ({len(udsnit)} måneder)")

samlet, normal = udsnit["Antal graddage"].sum(), udsnit["Normal"].sum()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Graddage i alt", f"{samlet:,}".replace(",", "."))
k2.metric("Normal i alt", f"{normal:,}".replace(",", "."))
k3.metric("Afvigelse", f"{samlet - normal:+,}".replace(",", "."))
k4.metric("Afvigelse i %", f"{(samlet - normal) / normal * 100:+.1f} %")

tab_graf, tab_år, tab_afv, tab_tabel = st.tabs(
    ["Graddage vs. normal", "År side om side", "Afvigelse", "Tabel"]
)
rækkefølge = udsnit["Måned"].tolist()

with tab_graf:
    basis = alt.Chart(udsnit).encode(x=alt.X("Måned:N", sort=rækkefølge, title=None))
    søjler = basis.mark_bar(opacity=0.85).encode(
        y=alt.Y("Antal graddage:Q", title="Graddage"),
        tooltip=["Måned", "Antal graddage", "Normal", "Afvigelse"],
    )
    linje = basis.mark_line(color="red", point=True).encode(y="Normal:Q")
    st.altair_chart((søjler + linje).properties(height=380), use_container_width=True)
    st.caption("Søjler: faktiske graddage. Rød linje: normal.")

with tab_år:
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
        farve = alt.Color("År:N", title="År")

        st.subheader("Graddage pr. måned")
        linjer = alt.Chart(år_df).mark_line(point=True).encode(
            x=x, y=alt.Y("Antal graddage:Q", title="Graddage"), color=farve,
            tooltip=["År", "Md", "Antal graddage", "Normal"],
        )
        norm = alt.Chart(normal_df).mark_line(color="black", strokeDash=[6, 4]).encode(
            x=x, y="Normal:Q", tooltip=["Md", "Normal"],
        )
        st.altair_chart((linjer + norm).properties(height=350), use_container_width=True)
        st.caption("Stiplet sort linje: normal.")

        st.subheader("Akkumuleret gennem året")
        kum = alt.Chart(år_df).mark_line(point=True).encode(
            x=x, y=alt.Y("Kumulativ:Q", title="Graddage (akkumuleret)"), color=farve,
            tooltip=["År", "Md", "Kumulativ"],
        )
        kum_norm = alt.Chart(normal_df).mark_line(color="black", strokeDash=[6, 4]).encode(
            x=x, y="Kumulativ normal:Q", tooltip=["Md", "Kumulativ normal"],
        )
        st.altair_chart((kum + kum_norm).properties(height=350), use_container_width=True)
        st.caption("Viser, hvordan hvert år hober sig op i forhold til normalen. "
                   "Et år med manglende måneder (fx 2026) stopper ved sidste kendte måned.")

with tab_afv:
    afv = alt.Chart(udsnit).mark_bar().encode(
        x=alt.X("Måned:N", sort=rækkefølge, title=None),
        y=alt.Y("Afvigelse:Q", title="Faktisk − normal"),
        color=alt.condition(alt.datum.Afvigelse > 0, alt.value("#d62728"), alt.value("#1f77b4")),
        tooltip=["Måned", "Afvigelse", "Afvigelse %"],
    )
    st.altair_chart(afv.properties(height=380), use_container_width=True)
    st.caption("Rød = koldere end normalt (flere graddage). Blå = varmere end normalt.")

with tab_tabel:
    vis = udsnit[["Måned", "Antal graddage", "Normal", "Afvigelse", "Afvigelse %"]]
    st.dataframe(vis, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Download udsnit som CSV",
        vis.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="graddage_udsnit.csv",
        mime="text/csv",
    )
