"""
DASHBOARD INTERAKTIF - JUMLAH KENDARAAN TERDAFTAR PER KELURAHAN
Kota Bogor - Tahun 2022, 2023, 2024, 2025
================================================================

Cara pakai:
1. Install library yang dibutuhkan (sekali saja):
   pip install streamlit pandas geopandas plotly

   Kalau geopandas susah install di Windows, pakai:
   pip install streamlit pandas plotly pyshp shapely pyproj

2. Pastikan struktur folder:
   project/
   ├── app.py              <- file ini
   └── data/
       ├── 2022.csv
       ├── 2023.csv
       ├── 2024.csv
       ├── 2025.csv
       └── kelurahan.shp (+ .shx, .dbf, .prj, dst)

3. Jalankan (BUKAN dengan "python app.py", tapi):
   streamlit run app.py

4. Browser akan otomatis terbuka ke http://localhost:8501
"""

import json
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ==================================================================
# KONFIGURASI - ganti warna dashboard di sini
# ==================================================================
WARNA_TEMA = "#0E7C7B"          # warna utama (header, tombol aktif)
WARNA_TEMA_MUDA = "#A8DADC"     # warna aksen muda
SKALA_WARNA_PETA = "Teal"       # skema warna choropleth: Blues, Greens, Reds, Viridis, Teal, dll
                                  # cek pilihan lain di: https://plotly.com/python/builtin-colorscales/

DATA_DIR = "."
SHAPEFILE_PATH = os.path.join(DATA_DIR, "kelurahan.shp")
CSV_FILES = {
    2022: os.path.join(DATA_DIR, "2022.csv"),
    2023: os.path.join(DATA_DIR, "2023.csv"),
    2024: os.path.join(DATA_DIR, "2024.csv"),
    2025: os.path.join(DATA_DIR, "2025.csv"),
}
FIELD_NAMA_KELURAHAN = "DESA_KELUR"
FIELD_NAMA_KECAMATAN = "KECAMATAN"

st.set_page_config(
    page_title="Dashboard Kendaraan Kota Bogor",
    page_icon="🚗",
    layout="wide",
)


# ==================================================================
# UTIL
# ==================================================================
def normalize_name(name: str) -> str:
    return str(name).strip().upper().replace(" ", "")


# ==================================================================
# LOAD DATA (di-cache supaya gak diulang setiap interaksi)
# ==================================================================
@st.cache_data
def load_data_kendaraan():
    semua = []
    for tahun, path in CSV_FILES.items():
        df = pd.read_csv(path, sep=";", encoding="latin1")
        df["tahun"] = tahun
        df["kel_key"] = df["Kelurahan"].apply(normalize_name)
        semua.append(df)
    return pd.concat(semua, ignore_index=True)


@st.cache_data
def load_geojson():
    try:
        import geopandas as gpd

        gdf = gpd.read_file(SHAPEFILE_PATH)
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        geojson = json.loads(gdf.to_json())
    except ImportError:
        import shapefile  # pyshp

        sf = shapefile.Reader(SHAPEFILE_PATH)
        fields = [f[0] for f in sf.fields[1:]]
        features = []
        for sr in sf.shapeRecords():
            geom = sr.shape.__geo_interface__
            attrs = dict(zip(fields, sr.record))
            features.append({"type": "Feature", "geometry": geom, "properties": attrs})
        geojson = {"type": "FeatureCollection", "features": features}

    # tambahkan key normalisasi nama ke setiap feature, buat join sama data CSV
    for feature in geojson["features"]:
        nama = feature["properties"].get(FIELD_NAMA_KELURAHAN, "")
        feature["properties"]["kel_key"] = normalize_name(nama)
        feature["id"] = feature["properties"]["kel_key"]

    return geojson


df_kendaraan = load_data_kendaraan()
geojson = load_geojson()

daftar_kelurahan = sorted({f["properties"][FIELD_NAMA_KELURAHAN] for f in geojson["features"]})
daftar_kecamatan = sorted({f["properties"][FIELD_NAMA_KECAMATAN] for f in geojson["features"]})
daftar_tahun = sorted(CSV_FILES.keys())


# ==================================================================
# SIDEBAR - MENU & FILTER
# ==================================================================
st.sidebar.markdown(f"<h2 style='color:{WARNA_TEMA};'>🚗 Dashboard Kendaraan</h2>", unsafe_allow_html=True)
st.sidebar.caption("Kota Bogor - Data Registrasi Kendaraan Roda 4")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Menu",
    ["🏠 Beranda", "🗺️ Peta Interaktif", "📊 Statistik", "📋 Data Tabel"],
)

st.sidebar.markdown("---")
st.sidebar.markdown("**Filter**")
tahun_pilih = st.sidebar.selectbox("Pilih Tahun", daftar_tahun, index=len(daftar_tahun) - 2)
kecamatan_pilih = st.sidebar.multiselect("Filter Kecamatan (opsional)", daftar_kecamatan, default=[])


# ==================================================================
# HITUNG AGREGAT SESUAI FILTER
# ==================================================================
def hitung_jumlah_per_kelurahan(tahun: int, kecamatan_filter: list) -> pd.DataFrame:
    df = df_kendaraan[df_kendaraan["tahun"] == tahun]
    agg = df.groupby("kel_key").size().reset_index(name="jumlah")

    # mapping nama asli kelurahan & kecamatan dari geojson
    mapping = {
        f["properties"]["kel_key"]: (
            f["properties"][FIELD_NAMA_KELURAHAN],
            f["properties"][FIELD_NAMA_KECAMATAN],
        )
        for f in geojson["features"]
    }
    agg["kelurahan"] = agg["kel_key"].map(lambda k: mapping.get(k, ("", ""))[0])
    agg["kecamatan"] = agg["kel_key"].map(lambda k: mapping.get(k, ("", ""))[1])

    if kecamatan_filter:
        agg = agg[agg["kecamatan"].isin(kecamatan_filter)]

    return agg


def hitung_semua_tahun() -> pd.DataFrame:
    semua = []
    for tahun in daftar_tahun:
        agg = hitung_jumlah_per_kelurahan(tahun, [])
        agg["tahun"] = tahun
        semua.append(agg)
    return pd.concat(semua, ignore_index=True)


# ==================================================================
# HALAMAN: BERANDA
# ==================================================================
if menu == "🏠 Beranda":
    st.markdown(f"<h1 style='color:{WARNA_TEMA};'>Dashboard Jumlah Kendaraan Terdaftar</h1>", unsafe_allow_html=True)
    st.markdown("##### Kota Bogor — Tahun 2022 s.d. 2025")
    st.write(
        "Dashboard ini menampilkan persebaran jumlah kendaraan roda 4 yang terdaftar "
        "di setiap kelurahan Kota Bogor. Gunakan menu di sidebar kiri untuk melihat "
        "peta interaktif, statistik, maupun data mentahnya."
    )

    agg_tahun_ini = hitung_jumlah_per_kelurahan(tahun_pilih, kecamatan_pilih)
    total_semua_tahun = hitung_semua_tahun()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Kendaraan", f"{agg_tahun_ini['jumlah'].sum():,}", help=f"Tahun {tahun_pilih}")
    col2.metric("Jumlah Kelurahan", f"{agg_tahun_ini.shape[0]}")
    kel_tertinggi = agg_tahun_ini.sort_values("jumlah", ascending=False).iloc[0]
    col3.metric("Kelurahan Tertinggi", kel_tertinggi["kelurahan"], f"{kel_tertinggi['jumlah']:,}")
    rata2 = agg_tahun_ini["jumlah"].mean()
    col4.metric("Rata-rata per Kelurahan", f"{rata2:,.0f}")

    st.markdown("---")
    st.subheader("Tren Total Kendaraan per Tahun (Semua Kelurahan)")
    tren = total_semua_tahun.groupby("tahun")["jumlah"].sum().reset_index()
    fig = px.bar(
        tren, x="tahun", y="jumlah", text="jumlah",
        color_discrete_sequence=[WARNA_TEMA],
    )
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig.update_layout(yaxis_title="Jumlah Kendaraan", xaxis_title="Tahun")
    st.plotly_chart(fig, use_container_width=True)


# ==================================================================
# HALAMAN: PETA INTERAKTIF
# ==================================================================
elif menu == "🗺️ Peta Interaktif":
    st.markdown(f"<h1 style='color:{WARNA_TEMA};'>Peta Interaktif</h1>", unsafe_allow_html=True)
    st.caption(f"Menampilkan data tahun **{tahun_pilih}** — basemap OpenStreetMap")

    agg = hitung_jumlah_per_kelurahan(tahun_pilih, kecamatan_pilih)

    fig = px.choropleth_mapbox(
        agg,
        geojson=geojson,
        locations="kel_key",
        featureidkey="properties.kel_key",
        color="jumlah",
        color_continuous_scale=SKALA_WARNA_PETA,
        mapbox_style="open-street-map",
        zoom=11.3,
        center={"lat": -6.5950, "lon": 106.8166},
        opacity=0.75,
        hover_name="kelurahan",
        hover_data={"kecamatan": True, "jumlah": True, "kel_key": False},
        labels={"jumlah": "Jumlah Kendaraan"},
    )
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=600)
    st.plotly_chart(fig, use_container_width=True)

    st.info("Geser pilih tahun & kecamatan di sidebar kiri untuk memperbarui peta ini.")


# ==================================================================
# HALAMAN: STATISTIK
# ==================================================================
elif menu == "📊 Statistik":
    st.markdown(f"<h1 style='color:{WARNA_TEMA};'>Statistik & Perbandingan</h1>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["Top Kelurahan", "Tren per Kelurahan", "Perbandingan Kecamatan"])

    # ---- TAB 1: TOP KELURAHAN ----
    with tab1:
        st.subheader(f"10 Kelurahan dengan Kendaraan Terbanyak — Tahun {tahun_pilih}")
        agg = hitung_jumlah_per_kelurahan(tahun_pilih, kecamatan_pilih)
        top10 = agg.sort_values("jumlah", ascending=False).head(10)
        fig_top = px.bar(
            top10, x="jumlah", y="kelurahan", orientation="h",
            color="jumlah", color_continuous_scale=SKALA_WARNA_PETA,
            text="jumlah",
        )
        fig_top.update_traces(texttemplate="%{text:,}", textposition="outside")
        fig_top.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Jumlah Kendaraan", yaxis_title="")
        st.plotly_chart(fig_top, use_container_width=True)

    # ---- TAB 2: TREN PER KELURAHAN (diagram perbedaan tahun) ----
    with tab2:
        st.subheader("Perbandingan Jumlah Kendaraan per Tahun untuk 1 Kelurahan")
        kelurahan_pilih = st.selectbox("Pilih Kelurahan", daftar_kelurahan)

        total_semua = hitung_semua_tahun()
        data_kel = total_semua[total_semua["kelurahan"] == kelurahan_pilih].sort_values("tahun")

        fig_tren = go.Figure()
        fig_tren.add_trace(go.Bar(
            x=data_kel["tahun"].astype(str), y=data_kel["jumlah"],
            marker_color=WARNA_TEMA, text=data_kel["jumlah"], texttemplate="%{text:,}",
            textposition="outside", name="Jumlah Kendaraan",
        ))
        fig_tren.update_layout(
            title=f"Jumlah Kendaraan Terdaftar — {kelurahan_pilih}",
            xaxis_title="Tahun", yaxis_title="Jumlah Kendaraan",
        )
        st.plotly_chart(fig_tren, use_container_width=True)

        # tabel perubahan (selisih tahun ke tahun)
        data_kel = data_kel.reset_index(drop=True)
        data_kel["selisih"] = data_kel["jumlah"].diff()
        st.dataframe(
            data_kel[["tahun", "jumlah", "selisih"]].rename(
                columns={"tahun": "Tahun", "jumlah": "Jumlah Kendaraan", "selisih": "Selisih dari Tahun Sebelumnya"}
            ),
            use_container_width=True,
            hide_index=True,
        )

    # ---- TAB 3: PERBANDINGAN KECAMATAN ----
    with tab3:
        st.subheader(f"Total Kendaraan per Kecamatan — Tahun {tahun_pilih}")
        agg = hitung_jumlah_per_kelurahan(tahun_pilih, [])
        per_kec = agg.groupby("kecamatan")["jumlah"].sum().reset_index().sort_values("jumlah", ascending=False)
        fig_kec = px.bar(
            per_kec, x="kecamatan", y="jumlah", color="jumlah",
            color_continuous_scale=SKALA_WARNA_PETA, text="jumlah",
        )
        fig_kec.update_traces(texttemplate="%{text:,}", textposition="outside")
        fig_kec.update_layout(xaxis_title="Kecamatan", yaxis_title="Jumlah Kendaraan")
        st.plotly_chart(fig_kec, use_container_width=True)


# ==================================================================
# HALAMAN: DATA TABEL
# ==================================================================
elif menu == "📋 Data Tabel":
    st.markdown(f"<h1 style='color:{WARNA_TEMA};'>Data Tabel</h1>", unsafe_allow_html=True)

    agg = hitung_jumlah_per_kelurahan(tahun_pilih, kecamatan_pilih)
    agg_tampil = agg[["kecamatan", "kelurahan", "jumlah"]].sort_values("jumlah", ascending=False)
    agg_tampil.columns = ["Kecamatan", "Kelurahan", "Jumlah Kendaraan"]

    st.write(f"Menampilkan {agg_tampil.shape[0]} kelurahan untuk tahun **{tahun_pilih}**")
    st.dataframe(agg_tampil, use_container_width=True, hide_index=True)

    csv = agg_tampil.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download data ini sebagai CSV",
        data=csv,
        file_name=f"kendaraan_per_kelurahan_{tahun_pilih}.csv",
        mime="text/csv",
    )
