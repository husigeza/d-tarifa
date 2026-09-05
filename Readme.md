# ⚡ E-ON D-Tarifa Kalkulátor

## Összefoglalás
Ez az interaktív webalkalmazás segít kiszámolni, hogyan alakulna a villanyszámlád a hagyományos (A1) és az új dinamikus (D) árszabás szerint. Az E-ON távleolvasási portáljáról letöltött 15 perces fogyasztási adatok alapján a program automatikusan lekéri az adott napokra érvényes MNB devizaárfolyamokat, valamint a HUPX (magyar villamosenergia-tőzsde) órás árait. Ezután negyedórás, idősoros pontossággal kiszámolja a sávhatár feletti fogyasztás valós költségét a D tarifa szabályai szerint, és interaktív grafikonon vizualizálja az eredményt.

## 🌐 Próbáld ki online (Live Demo)
Az alkalmazás telepítés nélkül is elérhető és kipróbálható az alábbi linken:
**[E-ON D-Tarifa Kalkulátor ](https://d-tarifa-gbthkjck9ylsloyrlhzusk.streamlit.app/)**

---

## 📥 E-ON adatok exportálása
A kalkulátor használatához saját fogyasztási adatokra lesz szükség. Ezeket az alábbi lépésekkel tudod kinyerni az E-ON rendszeréből:

1. Lépj be az **E-ON Távleolvasási portáljára**.
2. Állítsd be a lekérdezni kívánt időszakot (a legátláthatóbb eredményekért **1 hónapos** időszak kiválasztása javasolt).
3. A periódusnál válaszd a **15 perces** bontást.
4. A *'Mérőváltozó(k) megadása'* beállításnál kizárólag a **+A** (hálózatból vételezett aktív energia) opciót jelöld ki.
5. Exportáld az adatokat XLSX formátumban. Ezt a fájlt kell feltölteni az alkalmazásba.

---

## 💻 Lokális futtatás
A projekt futtatásához Python 3.9+ környezet ajánlott.

```bash
# Függőségek telepítése
pip3 install -r requirements.txt

# Alkalmazás indítása
python3 -m streamlit run app.py
 ```

Az alkalmazás a http://localhost:8501 címen lesz elérhető.

---

## ⚠️ Felelősségkizárás
Ez az alkalmazás a Gemini AI segítségével készült, kódja és számítási logikája nem tesztelt. Az automatikusan importált külső adatsorok (MNB EUR-HUF árfolyam, Fraunhofer HUPX tőzsdei árak) nem ellenőrzöttek, és a kiszámolt áramszámla pontosságára nincs semmilyen garancia. A szerző az alkalmazás által mutatott információkért és az esetlegesen ebből fakadó anyagi vagy egyéb döntésekért semmilyen felelősséget nem vállal. Az eszköz kizárólag tájékoztató jellegű, oktatási és hobbiprojekt céljából készült.