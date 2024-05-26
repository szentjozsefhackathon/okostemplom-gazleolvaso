## Gázóra leolvasó
# Szükséges:
 - pytesseract (this is a wrapper for Google's Tesseract-OCR Engine)
 - opencv-python
 - numpy
 - flask

# Használat:
 - Elegendő meghívni a detection.py detection() functiont, ami visszaad egy 5 hosszú listát a számokkal
 - Konzolbeli vizualizációhoz elegendő futtatni a cli.py-t ´python3 cli.py´
 - Webfelületen történő vizuálizációhoz futtatni: ´flask --app main run´

# Eredmény
 - ?: a pytesseract nem tudta leolvasni azt a számot
 - !: az RTSP nem adott vissza képet
 - kisebb pontatlanságok előfordulhatnak

A program a gázóra leolvasását egy RTPS szerver élő adást adó kamera segítségével teszi meg. A kapott képet egy maszk majd további képmanipulációk segítségével átalakítja és lefutattja a pytesseract image_to_stringet. Ezután egy számsort ad, amelyet egy webszerveren jelenít meg. A maszkolás sajnos nem dinamikus, a maszkot egy külön fájlból kapja a program. Evégett a kamera egyhelyben maradása a program helyes működéséhez fontos.