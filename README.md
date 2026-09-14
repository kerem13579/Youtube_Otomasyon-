# TrueAmerican DIY Shorts — otomasyon

Her sabah 06:00'da Telegram'a analiz + 5 fikir yollar. Bir fikre basarsın;
prompt yazılır, video üretilir, abone-ol animasyonu bindirilir, YouTube'a
yüklenir ve ABD izlenme saatinde tam o dakikada yayına girer.

GitHub Actions üstünde çalışır. Senin bilgisayarının açık olması gerekmez.

**Kurulum: [docs/SETUP.md](docs/SETUP.md)** — 30-40 dakika, bir kere.

---

## Ne neyi yapıyor

| Dosya | İş |
|---|---|
| `bot/brief.py` | Sabah 06:00 mesajı: son 3 günün haberi, faktör analizi, yayın saati, 5 fikir |
| `bot/poll.py` | Telegram'ı 5 dakikada bir dinler, butona basınca pipeline'ı başlatır |
| `bot/pipeline.py` | Fikir → prompt → video → bindirme → yükleme → kuyruk |
| `bot/publish.py` | Hedef saatte gizli videoyu tam o saniyede herkese açar |
| `bot/analytics.py` | Neyin işe yaradığını ve en iyi yayın saatini kanalın kendi verisinden öğrenir |
| `bot/metadata.py` | Başlık/açıklama/etiket üretimi ve tekrar engelleme |
| `bot/prompts.py` | Seedance JSON prompt'unu ve metin parçalarını yazdırır |
| `bot/editor.py` | ffmpeg: chromakey bindirme, 1080x1920 upscale, sessizlik kontrolü |

Durum `data/` altındaki JSON dosyalarında tutulur ve her çalıştırmadan sonra
depoya geri commit edilir. Ayrı veritabanı yok.

---

## Kanalın verisinden çıkan kurallar

25 videoluk veri seti (2026-08-17 → 09-14) üstünde hesaplandı. Kod bu
kuralları uygular, temenni olarak bırakmaz.

**1. Retention her şey. Kapak neredeyse hiçbir şey.**

| Metrik | İzlenmeyle korelasyon |
|---|---|
| İzlemeye devam edenler % | **r = +0.73** |
| Ortalama görüntüleme % | r = +0.56 |
| Video süresi | r = −0.38 |
| Küçük resim tıklama oranı | r = +0.14 |

Retention'ı %68'in üstünde olan hiçbir video 12.700'ün altına düşmedi;
%62'nin altında olan hiçbiri (şemsiye hariç) 3.000'i geçemedi. Shorts akışından
gelen izlenmede kapak tıklaması neredeyse anlamsız — bu yüzden kod, kapağa
değil ilk üç saniyeye yatırım yapar.

**2. Ölçek ve su her şeyi yener.**

| Fikir tipi | Medyan izlenme |
|---|---|
| Büyük ev eşyası → su öğesi | 95.000 – 644.000 |
| Yıpranmış obje → taş | 18.000 – 29.000 |
| Sıfırdan inşa / küçük aksesuar | 2.600 – 5.100 |

`ideas.py` bu sıralamayı fikir üretim istemine gömer ve her turda en az iki
TIER 1 fikir ister.

**3. Süre 31 saniyeyi geçmemeli.** 33-35 saniyelik yüklemelerin **hepsi**
tabloda en dipte.

**4. Sonucu söyleyen başlık öldürür.** `Why Didn't I Think of This? Concrete
Handbag Planter!` tam olarak ne olduğunu söylüyor ve 2.768 aldı. En iyi iki
başlık sonucu saklıyor.

**5. Tekrar yamyamlık yapar.** Aynı başlıkla ikinci eldiven videosu 28.256'ya
karşı 1.506 aldı. Bu yüzden başlık kalıbı 12, kalıp ailesi 4 video boyunca
kilitli.

---

## Başlık ve açıklama rotasyonu

`data/title_patterns.json` — **25 kalıp, 7 aile**:

| Aile | Örnek |
|---|---|
| `imperative_save` | Don't Throw Away Old Watering Cans! Turn Them Into This! 🤯 |
| `first_person_act` | I Poured Concrete Into an Old Shopping Trolley - The Result Is Genius |
| `transformation_gap` | From Old Step Ladder to Solid Stone - Wait Till You See It |
| `question_hook` | Why Didn't Anyone Tell Me Old Wheelbarrows Could Do This? 🤯 |
| `hidden_value` | That Old Step Ladder in Your Garage Is Worth Keeping 🤯 |
| `warning_before` | Before You Throw Out That Old Shopping Trolley, Watch This 🤯 |
| `reveal_tease` | An Old Suitcase Went In. Something Else Came Out 🤯 |

Kurallar kodla zorlanıyor: sonucu asla söyleme, en fazla bir emoji, `|` yok,
ALL CAPS yok, başlıkta hashtag yok, 30-90 karakter. Kanalın kanıtlanmış A1
kalıbı rotasyonda kalır ama artık payını üçte birle sınırlar.

40 uploadlık simülasyonda 22-24 farklı kalıp kullanıldı, hiçbir kalıp 12 video
içinde, hiçbir aile 4 video içinde tekrarlamadı.

`data/desc_patterns.json` — 12 açılış cümlesi, 8 yorum sorusu, 4 "no talking"
cümlesi, 5 hashtag seti. Yapı sabit (ilk 125 karakter arama sonucunda görünen
tek kısım), içindeki her cümle döner.

`data/tag_vocabulary.json` — vidIQ'da doğrulanmış hacimli kelimeler. `decor`
ailesi kara listede (bu nişte 17-51 puan alırken `craft`/`upcycle` 61-66
alıyor), sıfır hacimli obje etiketleri de öyle. Her sette ~480 karakter dolar.

---

## "Şaheserler artık özgün değil" için ne değişti

`bot/prompts.py` içindeki dört zorunlu kural:

1. `critical_detail` **o objeye özgü** hayatta kalan detayı ismen söylemek
   zorunda — botun dikişi ve halkaları, sulama kabının perçini, lastiğin diş
   blokları. "Düzgünce kaplandı" kabul edilmiyor; asıl hata o.
2. Bitmiş parçada seri üretim bir bahçe süsünde olmayacak **tek bir imza
   dokunuş** olmak zorunda — elle çizilmiş motif, kasıtlı iki tonlu kenar,
   çatlağa bastırılmış yosun, parlatılmış ağız, kakma çakıl hattı.
3. **Kusurlar açıkça isteniyor**: düzensiz boya, mala izleri, kenara basılmış
   parmak izi, bir yandan akan damlalar, çimende kuru harç kırıntıları. Bu
   olmadan çıktı ürün fotoğrafına benziyor ve işçilik sahte duruyor.
4. Bitmiş yüksekliği kadının boyuna göre belirtmek zorunlu, yoksa model küçük
   el işini mimariye çeviriyor.

---

## Yayın saati nasıl belirleniyor

YouTube Analytics'te **saat boyutu yok** — "videolarım hangi saatte izlendi"
API'den cevaplanamaz. Cevaplanabilen ve zaten kararı veren şey şu: *hangi
saatte yayınlanan video ilk 48 saatte ne yaptı.*

`analytics.best_publish_hour()` her videonun gerçek `publishedAt` saatini (ABD
Doğu saatine çevirip) ilk 48 saatlik izlenmesiyle eşler ve **medyanı** en
yüksek saati seçer — tek bir 644K'lık aykırı değer takvimi belirlemesin diye
ortalama değil medyan.

En az 8 yerleşmiş video olana kadar `SEED_PUBLISH_HOUR_ET` (varsayılan 16:00
ET) kullanılır ve sabah mesajı bunu açıkça "henüz öğrenmedi" diye yazar.
Başlangıç değeri, birden çok Shorts zamanlama çalışmasının hafta içi
14:00-18:00 ET aralığında buluşmasından geliyor — ama kanalın kendi verisi
geldiği anda onun yerini alır.

Yayın, YouTube'un kendi zamanlayıcısıyla değil, videoyu gizli yükleyip hedef
saniyede herkese açarak yapılır.
