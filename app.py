import streamlit as st
import pandas as pd
import numpy as np
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="E-ON D-Tarifa Kalkulátor", layout="wide")

st.title("⚡ Valós idejű E-ON D-Tarifa vs. A1 Árszabás Kalkulátor")
st.markdown("""
Töltsd fel az E-ON távleolvasási portálról letöltött 15 perces felbontású fogyasztási adatokat (XLSX vagy CSV formátum).
Az alkalmazás automatikusan felismeri az időszakot, és bekéri a szükséges **MNB EUR/HUF deviza középárfolyamot** 
és a **HUPX DAM árakat**, majd **negyedórás pontossággal, időrendben** számolja ki a valós D tarifa költséget.
""")

# --- BEÁLLÍTÁSOK / PARAMÉTEREK ---
with st.sidebar:
    st.header("⚙️ Tarifális paraméterek")
    st.info("Az MVM Next és az MEKH publikus adatai alapján.")
    
    a1_kedv_ar_brutto = st.number_input("A1 kedvezményes ár (Bruttó Ft/kWh)", value=36.0, step=0.1)
    a1_piaci_ar_brutto = st.number_input("A1 piaci ár (Bruttó Ft/kWh)", value=70.1, step=0.1)
    napi_keret_kwh = st.number_input("Napi kedvezményes keret (kWh)", value=6.91, step=0.01)
    
    st.markdown("---")
    st.markdown("### D Tarifa Részletek")
    kereskedoi_dij_netto = st.number_input("MVM Kereskedői díj (Nettó Ft/kWh)", value=4.5, step=0.1)
    rhd_netto = st.number_input("Rendszerhasználati díj (Nettó Ft/kWh)", value=23.4, step=0.1)
    afa_kulcs = st.number_input("ÁFA kulcs (%)", value=27.0, step=1.0)

# --- API FÜGGVÉNYEK ---

@st.cache_data(ttl=3600)
def get_mnb_exchange_rates(start_date, end_date):
    try:
        url = 'http://www.mnb.hu/arfolyamok.asmx'
        headers = {'Content-Type': 'text/xml; charset=utf-8'}
        body = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://www.mnb.hu/webservices/">
           <soapenv:Header/>
           <soapenv:Body>
              <tem:GetExchangeRates>
                 <tem:startDate>{start_date.strftime('%Y-%m-%d')}</tem:startDate>
                 <tem:endDate>{end_date.strftime('%Y-%m-%d')}</tem:endDate>
                 <tem:currencyNames>EUR</tem:currencyNames>
              </tem:GetExchangeRates>
           </soapenv:Body>
        </soapenv:Envelope>"""
        response = requests.post(url, data=body, headers=headers, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            result = root.find('.//{http://www.mnb.hu/webservices/}GetExchangeRatesResult').text
            if result:
                res_root = ET.fromstring(result)
                dates, rates = [], []
                for day in res_root.findall('Day'):
                    date_str = day.get('date')
                    rate_str = day.find('Rate').text.replace(',', '.')
                    dates.append(datetime.strptime(date_str, '%Y-%m-%d').date())
                    rates.append(float(rate_str))
                
                df_rates = pd.DataFrame({'Datum': dates, 'EUR_HUF': rates}).set_index('Datum')
                all_dates = pd.date_range(start=start_date, end=end_date).date
                df_all = pd.DataFrame(index=all_dates)
                return df_all.join(df_rates).ffill().bfill() 
    except Exception as e:
        st.warning(f"Nem sikerült letölteni az MNB árfolyamokat. Hiba: {e}")
    
    st.info("Alapértelmezett 395 HUF/EUR árfolyamot használunk hiba miatt.")
    all_dates = pd.date_range(start=start_date, end=end_date).date
    return pd.DataFrame({'EUR_HUF': [395.0] * len(all_dates)}, index=all_dates)

@st.cache_data(ttl=3600)
def get_hupx_prices(start_date, end_date):
    try:
        url = 'https://api.energy-charts.info/price'
        params = {
            'bzn': 'HU',
            'start': start_date.strftime('%Y-%m-%d'),
            'end': (end_date + timedelta(days=1)).strftime('%Y-%m-%d')
        }
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            df_prices = pd.DataFrame({
                'unix_seconds': data['unix_seconds'],
                'HUPX_EUR_MWh': data['price']
            })
            
            df_prices['Datum_Ido'] = pd.to_datetime(df_prices['unix_seconds'], unit='s', utc=True)
            df_prices['Datum_Ido'] = df_prices['Datum_Ido'].dt.tz_convert('Europe/Budapest').dt.tz_localize(None)
            
            df_prices = df_prices.set_index('Datum_Ido')[['HUPX_EUR_MWh']]
            df_resampled = df_prices.resample('15min').ffill()
            return df_resampled
        else:
            st.error(f"Hiba a HUPX adatok letöltésekor. Kód: {response.status_code}")
    except Exception as e:
        st.error(f"API hiba a HUPX adatok letöltésekor: {e}")
        
    return None

# --- FÁJL FELTÖLTÉSE ---
uploaded_file = st.file_uploader("📂 E-ON Excel vagy CSV export feltöltése", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=3, names=["Datum_Ido", "Fogyasztas_kWh"])
            df['Datum_Ido'] = pd.to_datetime(df['Datum_Ido'], format='%Y.%m.%d. %H:%M')
        else:
            df = pd.read_excel(uploaded_file, skiprows=2, names=["Datum_Ido", "Fogyasztas_kWh"])
            df = df[~df['Datum_Ido'].astype(str).str.contains('MAXIMUM|ÖSSZEG|Dátum', na=False, case=False)].copy()
            try:
                df['Datum_Ido'] = pd.to_datetime(df['Datum_Ido'], format='%Y.%m.%d. %H:%M')
            except:
                df['Datum_Ido'] = pd.to_datetime(df['Datum_Ido'])
                
        df['Fogyasztas_kWh'] = pd.to_numeric(df['Fogyasztas_kWh'], errors='coerce').fillna(0)
        
        min_date = df['Datum_Ido'].min().date()
        max_date = df['Datum_Ido'].max().date()
        napok_szama = (max_date - min_date).days + 1
        
        st.success(f"Adatok sikeresen beolvasva: **{min_date} - {max_date}** ({napok_szama} nap)")
        
        with st.spinner("API-k lekérdezése folyamatban (MNB, HUPX)..."):
            df_mnb = get_mnb_exchange_rates(min_date, max_date)
            df_hupx = get_hupx_prices(min_date, max_date)
        
        # --- ADATOK EGYESÍTÉSE ---
        df['Datum'] = df['Datum_Ido'].dt.date
        df = df.merge(df_mnb, left_on='Datum', right_index=True, how='left')
        
        if df_hupx is not None:
            df = df.set_index('Datum_Ido').join(df_hupx, how='left').reset_index()
            df['HUPX_EUR_MWh'] = df['HUPX_EUR_MWh'].ffill().bfill()
        else:
            st.error("Nem sikerült lekérni a piaci árakat. Az alkalmazás leállt.")
            st.stop()
            
        # --- KÖLTSÉGSZÁMÍTÁSOK ÉS SÁVHATÁROK ---
        afa_szorzo = 1.0 + (afa_kulcs / 100.0)
        idoszaki_keret = napok_szama * napi_keret_kwh
        
        # 1. Negyedórás Bruttó Dinamikus Ár (Ft/kWh)
        df['Napi_HUPX_Ft_kWh'] = (df['HUPX_EUR_MWh'] / 1000.0) * df['EUR_HUF']
        df['Brutto_Negyedoras_Ar_Ft_kWh'] = (df['Napi_HUPX_Ft_kWh'] + kereskedoi_dij_netto + rhd_netto) * afa_szorzo
        
        # 2. Idősoros (kronologikus) pontos D tarifa és A1 számítás
        # Kiszámítjuk a kumulált fogyasztást minden egyes 15 perces lépésben
        df['Kumulalt_Fogyasztas'] = df['Fogyasztas_kWh'].cumsum()
        
        # Meghatározzuk az egyes blokkokban érvényes tényleges árat és költséget
        # Előző kumulált fogyasztás a blokk elején
        df['Elözo_Kumulalt'] = df['Kumulalt_Fogyasztas'].shift(1).fillna(0)
        
        def calculate_exact_costs(row, limit, a1_price):
            cons = row['Fogyasztas_kWh']
            prev_cum = row['Elözo_Kumulalt']
            curr_cum = row['Kumulalt_Fogyasztas']
            dyn_price = row['Brutto_Negyedoras_Ar_Ft_kWh']
            
            if cons <= 0:
                return 0.0, 0.0, a1_price
                
            if curr_cum <= limit:
                # Teljesen a kedvezményes sávban van
                cost_d = cons * a1_price
                applied_price = a1_price
            elif prev_cum >= limit:
                # Teljesen a sávhatár felett van (pontos negyedórás dinamikus ár)
                cost_d = cons * dyn_price
                applied_price = dyn_price
            else:
                # Részben alatta, részben felette van ebben a 15 percben
                under_kwh = limit - prev_cum
                over_kwh = curr_cum - limit
                cost_d = (under_kwh * a1_price) + (over_kwh * dyn_price)
                # Grafikonhoz súlyozott átlagár erre a 15 percre
                applied_price = cost_d / cons
                
            return cost_d, applied_price
            
        # Alkalmazzuk soronként
        results = df.apply(lambda row: calculate_exact_costs(row, idoszaki_keret, a1_kedv_ar_brutto), axis=1)
        df['Negyedoras_D_Koltseg_Ft'] = [r[0] for r in results]
        df['Alkalmazott_Ar_Ft_kWh'] = [r[1] for r in results]
        
        tullepes = df[df['Kumulalt_Fogyasztas'] > idoszaki_keret]
        tullepes_idopontja = tullepes['Datum_Ido'].min() if not tullepes.empty else None
        
        teljes_fogyasztas = df['Fogyasztas_kWh'].sum()
        a1_kedvezmenyes_fogyasztas = min(teljes_fogyasztas, idoszaki_keret)
        a1_piaci_fogyasztas = max(0, teljes_fogyasztas - idoszaki_keret)
        
        # A1 Tarifa Költség
        a1_osszkoltseg = (a1_kedvezmenyes_fogyasztas * a1_kedv_ar_brutto) + (a1_piaci_fogyasztas * a1_piaci_ar_brutto)
        
        # D Tarifa Költség (A pontos, negyedórás idősoros összeg)
        d_tarifa_osszkoltseg = df['Negyedoras_D_Koltseg_Ft'].sum()
        
        # --- MEGJELENÍTÉS ---
        st.subheader("📊 Fogyasztási Összesítő")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Vizsgált időszak", f"{napok_szama} nap")
        col2.metric("Teljes fogyasztás", f"{teljes_fogyasztas:.2f} kWh")
        col3.metric("Átlagos HUPX ár", f"{df['HUPX_EUR_MWh'].mean():.2f} EUR/MWh")
        col4.metric("Időszaki sávhatár", f"{idoszaki_keret:.2f} kWh")
        
        st.markdown("---")
        res_col1, res_col2 = st.columns(2)
        
        with res_col1:
            st.success("### Hagyományos A1 Tarifa")
            st.metric("Becsült fizetendő", f"{a1_osszkoltseg:,.0f} Ft".replace(',', ' '))
            st.write(f"**Kedvezményes sáv:** {a1_kedvezmenyes_fogyasztas:.2f} kWh ({a1_kedv_ar_brutto} Ft/kWh)")
            st.write(f"**Piaci sáv:** {a1_piaci_fogyasztas:.2f} kWh ({a1_piaci_ar_brutto} Ft/kWh)")
            
        with res_col2:
            if d_tarifa_osszkoltseg < a1_osszkoltseg:
                st.info("### 🟢 Dinamikus D Tarifa (Megéri)")
            else:
                st.warning("### 🔴 Dinamikus D Tarifa (Nem éri meg)")
                
            st.metric("Becsült fizetendő", f"{d_tarifa_osszkoltseg:,.0f} Ft".replace(',', ' '))
            st.write(f"**Kedvezményes sáv:** {a1_kedvezmenyes_fogyasztas:.2f} kWh")
            st.write(f"**Dinamikus sáv (pontos negyedórás):** {a1_piaci_fogyasztas:.2f} kWh")
            
        st.markdown("---")
        st.subheader("Fogyasztás és Alkalmazott Ár Alakulása (Idősoros elszámolás)")
        
        # --- KÖZÖS PLOTLY GRAFIKON LÉTREHOZÁSA ---
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # 1. Tengely: Fogyasztás (KÉK terület)
        fig.add_trace(
            go.Scatter(x=df['Datum_Ido'], y=df['Fogyasztas_kWh'], name="Fogyasztás (kWh)",
                       fill='tozeroy', line=dict(color='blue', width=1)),
            secondary_y=False,
        )
        
        # 2. Tengely: Alkalmazott Ár (ZÖLD bázis - A1 ár vagy piaci ár alatt)
        fig.add_trace(
            go.Scatter(x=df['Datum_Ido'], y=df['Alkalmazott_Ar_Ft_kWh'], name="D Tarifa ár (A1 piaci ár alatt)",
                       line=dict(color='green', width=2)),
            secondary_y=True,
        )
        
        # Piros réteg rárajzolása a magas árakra
        is_high = df['Alkalmazott_Ar_Ft_kWh'] > a1_piaci_ar_brutto
        red_mask = is_high | is_high.shift(1).fillna(False) | is_high.shift(-1).fillna(False)
        
        df_red = df.copy()
        df_red.loc[~red_mask, 'Alkalmazott_Ar_Ft_kWh'] = np.nan
        
        fig.add_trace(
            go.Scatter(x=df_red['Datum_Ido'], y=df_red['Alkalmazott_Ar_Ft_kWh'], name="D Tarifa ár (A1 piaci ár felett)",
                       line=dict(color='red', width=2), connectgaps=False),
            secondary_y=True,
        )
        
        # Vízszintes vonal: A1 emelt árszint (piaci ár)
        fig.add_hline(y=a1_piaci_ar_brutto, line_width=2, line_dash="dash", line_color="gray", 
                      annotation_text=f"A1 piaci ár ({a1_piaci_ar_brutto} Ft)", annotation_position="top left",
                      secondary_y=True)

        # Függőleges vonal és felirat a sávhatár átlépéséhez (Szaggatott narancssárga)
        if tullepes_idopontja:
            fig.add_vline(x=tullepes_idopontja, line_width=2, line_dash="dash", line_color="orange")
            fig.add_annotation(x=tullepes_idopontja, y=1.05, yref='paper',
                               text="Sávhatár túllépése (D tarifa indul)", 
                               showarrow=False, font=dict(color="orange", size=12))
            
        fig.update_layout(
            height=550,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="right", x=1),
            margin=dict(l=0, r=0, t=60, b=0)
        )
        
        max_fogyasztas = df['Fogyasztas_kWh'].max()
        fig.update_yaxes(title_text="Fogyasztás (kWh)", range=[0, max_fogyasztas * 1.1], secondary_y=False, color="blue")
        fig.update_yaxes(title_text="Ár (Ft/kWh)", secondary_y=True, color="black")
        
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Hiba történt az adatok feldolgozásakor: {e}")