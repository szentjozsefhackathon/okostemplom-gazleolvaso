## Gázóra leolvasó
Szükséges:
    
 - pytesseract (this is a wrapper for Google's Tesseract-OCR Engine)
 - opencv-python
 - numpy
 - flask

A program a gázóra leolvasását egy RTPS szerver élő adást adó kamera segítségével teszi meg. A kapott képet egy maszk majd további képmanipulációk segítségével átalakítja és lefutattja a pytesseract image_to_stringet. Ezután egy számsort ad, amelyet egy webszerveren jelenít meg. A maszkolás sajnos nem dinamikus, a maszkot egy külön fájlból kapja a program. Evégett a kamera egyhelyben maradása a program helyes működéséhez fontos.