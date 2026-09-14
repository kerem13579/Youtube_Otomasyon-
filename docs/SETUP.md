# Kurulum

Toplam 30-40 dakika. Beş şey alacaksın, hepsini GitHub'a yapıştıracaksın, bitti.
Sıra önemli değil ama en zoru YouTube, onu sona bırakmak isteyebilirsin.

Bir kere kurulduktan sonra sistem GitHub'ın sunucularında çalışır. Senin
bilgisayarının açık olması gerekmez.

---

## 1. Telegram botu (3 dakika)

1. Telegram'da **@BotFather**'a yaz, `/newbot` gönder.
2. Bota bir isim ve `_bot` ile biten bir kullanıcı adı ver.
3. BotFather sana `123456789:AAH...` şeklinde bir **token** verir → bu
   `TELEGRAM_BOT_TOKEN`.
4. Kendi botuna git, `/start` yaz (bot sana yazabilsin diye bu şart).
5. Chat ID'ni öğrenmek için **@userinfobot**'a yaz. Verdiği sayı →
   `TELEGRAM_CHAT_ID`.

---

## 2. LLM anahtarı (2 dakika)

Fikirleri, video prompt'unu ve metinleri bu yazıyor. **Üç sağlayıcıdan birini
seçebilirsin** — kod hepsini destekliyor, aralarında geçiş tek bir değişkenle.

### OpenRouter (varsayılan, önerilen)

Tek anahtarla her modele erişiyorsun, model değiştirmek için yeni hesap
gerekmiyor.

1. <https://openrouter.ai> → Keys → anahtarı kopyala → `OPENROUTER_API_KEY`
2. Variables'a `LLM_PROVIDER` = `openrouter`
3. İstersen `LLM_MODEL` ile modeli seç. Varsayılan
   `anthropic/claude-sonnet-4.5`. Daha ucuz istersen
   `anthropic/claude-haiku-4.5` veya `google/gemini-2.5-flash`.

### Gemini (ücretsiz katman var)

1. <https://aistudio.google.com/apikey> → anahtar → `GEMINI_API_KEY`
2. `LLM_PROVIDER` = `gemini`, `LLM_MODEL` = `gemini-2.5-flash`

Bedava ama sert kurallı uzun sistem prompt'unu takip etmekte Sonnet'ten zayıf.
Video prompt'u kalitesi burada belirlendiği için ilk tercih olarak önermiyorum;
bütçe sıfırsa çalışır.

### Anthropic doğrudan

1. <https://console.anthropic.com> → API Keys → `ANTHROPIC_API_KEY`
2. `LLM_PROVIDER` = `anthropic`

### Maliyet

Bot günde ~3.700 girdi + ~4.550 çıktı token harcıyor (1 video). Sonnet
fiyatıyla günde ~5 sent, ayda ~$1.60. WaveSpeed render maliyetinin yanında
gürültü — burada tasarruf etmeye çalışma.

---

## 3. WaveSpeed (2 dakika)

1. WaveSpeed panelinde API anahtarını kopyala → `WAVESPEED_API_KEY`.
2. Kullandığın Seedance modelinin tam kimliğini not et. Panelde modelin
   sayfasındaki örnek istekte `api.wavespeed.ai/api/v3/` **sonrasında** gelen
   kısım budur, örneğin:

   ```
   https://api.wavespeed.ai/api/v3/bytedance/seedance-v2-pro
                                   ^^^^^^^^^^^^^^^^^^^^^^^^^
   ```

   Bu değer `WAVESPEED_MODEL` **variable**'ı olarak girilecek (secret değil).
   Boş bırakırsan `bytedance/seedance-v2-pro` denenir.

---

## 4. YouTube erişimi (15-20 dakika, en uzunu)

Videoyu yükleyen ve tam saatinde yayına alan kısım. Google Cloud'da bir kere
uygulama tanımlıyorsun.

> **`AIzaSy...` ile başlayan bir "YouTube API key" burada işe yaramaz.**
> O tür anahtar sadece **herkese açık** veriyi okur. Video yüklemek ve
> Analytics okumak kanal sahibi adına **OAuth** ister — yani aşağıdaki
> Client ID + Client secret + Refresh token üçlüsü. Elinde API key varsa
> onu at, aşağıdaki adımları yap.

### 4a. Projeyi ve API'leri aç

1. <https://console.cloud.google.com> → üstten **yeni proje** oluştur.
2. **APIs & Services → Library**. Şu ikisini bul ve **Enable** et:
   - `YouTube Data API v3`
   - `YouTube Analytics API`

### 4b. OAuth ekranını ayarla

1. **APIs & Services → OAuth consent screen**.
2. **External** seç, devam et.
3. Uygulama adı (ne olursa), destek e-postası ve iletişim e-postası: kendi
   adresin.
4. **Scopes** adımını atla, **Save**.
5. **Audience / Test users** bölümüne kendi Google hesabını **test user**
   olarak ekle. Bu adımı atlarsan token almaya çalışırken hata alırsın.
6. Uygulamayı *yayına alman gerekmez* — test modunda kalması yeterli. Tek
   dezavantajı refresh token'ın 7 günde bir sona ermesidir, o yüzden
   ekranı **Publish App** ile yayına almanı öneririm (doğrulama istemez,
   "Unverified" uyarısını geçersin).

### 4c. Kimlik bilgilerini oluştur

1. **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
2. Application type: **Desktop app**. İsim ne olursa.
3. Çıkan **Client ID** ve **Client secret** → `YT_CLIENT_ID`,
   `YT_CLIENT_SECRET`.

### 4d. Refresh token'ı üret

Bunu kendi bilgisayarında bir kere çalıştırıyorsun:

```bash
pip install requests
python tools/get_youtube_token.py
```

Client ID ve secret'ı sorar, tarayıcını açar, kanalını seçmeni ister. Sonunda
ekrana dört değeri birden basar:

```
Kanal: TrueAmerican
YT_CHANNEL_ID    UC-BXtsxzWD-QyWotA7J88aA
YT_CLIENT_ID     ...
YT_CLIENT_SECRET ...
YT_REFRESH_TOKEN 1//0g...
```

> Google izin ekranında "Google hasn't verified this app" uyarısı çıkarsa
> **Advanced → Go to ... (unsafe)** de. Kendi yazdığın uygulama, sorun değil.

---

## 5. GitHub'a gir (5 dakika)

Depoda **Settings → Secrets and variables → Actions**.

**Secrets** sekmesi (`New repository secret`):

| İsim | Nereden |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Adım 1 |
| `TELEGRAM_CHAT_ID` | Adım 1 |
| `OPENROUTER_API_KEY` | Adım 2 (hangi sağlayıcıyı seçtiysen o anahtar: `GEMINI_API_KEY` veya `ANTHROPIC_API_KEY`) |
| `WAVESPEED_API_KEY` | Adım 3 |
| `YT_CLIENT_ID` | Adım 4c |
| `YT_CLIENT_SECRET` | Adım 4c |
| `YT_REFRESH_TOKEN` | Adım 4d |

**Variables** sekmesi (`New repository variable`):

| İsim | Değer |
|---|---|
| `LLM_PROVIDER` | `openrouter` (ya da `gemini` / `anthropic`) |
| `LLM_MODEL` | boş bırakabilirsin — varsayılan `anthropic/claude-sonnet-4.5` |
| `YT_CHANNEL_ID` | `UC-BXtsxzWD-QyWotA7J88aA` |
| `WAVESPEED_MODEL` | Adım 3'teki model kimliği |

Kullanmadığın sağlayıcıların anahtarlarını hiç eklemene gerek yok.

---

## 6. Test et

1. Depoda **Actions** sekmesi → sol listeden **Self test** → **Run workflow**.
2. 1-2 dakika içinde Telegram'a bir rapor düşer:

```
🧪 Self-test sonucu

✅ Telegram — mesaj gönderildi
✅ LLM — openrouter / anthropic/claude-sonnet-4.5 -> OK
✅ YouTube auth — 25 video okundu, en yenisi: Don't Throw Away That Old...
✅ YouTube Analytics — son 14 gün: 412.883 görüntülenme
✅ WaveSpeed key — anahtar kabul edildi (HTTP 404)
✅ ffmpeg + bumper — 1080x1920, 30.0s
✅ Rotation data — B3 -> "I Dipped an Old..." (61 krktr) · 27 etiket / 470 krktr
```

Ayrıca abone-ol bindirmesinin nasıl göründüğünü gösteren küçük bir test videosu
gelir. Hepsi yeşilse sistem hazır.

Kırmızı varsa:

| Hata | Sebep |
|---|---|
| `Telegram ❌ chat not found` | Bota `/start` yazmayı unuttun |
| `YouTube auth ❌ invalid_grant` | Refresh token süresi dolmuş; 4d'yi tekrarla, OAuth ekranını Publish et |
| `WaveSpeed ❌ anahtar reddedildi` | Anahtar yanlış kopyalanmış |
| `LLM ❌ 401` | Anahtar yanlış, ya da OpenRouter/Anthropic bakiyesi bitmiş |

---

## 7. İlk gerçek çalıştırma

Sabah 06:00'ı beklemek istemiyorsan: **Actions → Morning brief → Run workflow**.
Telegram'a rapor + 5 fikir düşer, bir numaraya basarsın, gerisi akar.

---

## Günlük akış

```
06:00 TR   ┌─ Morning brief
           │  • son 3 günün videoları, izlenme ve abone rakamlarıyla
           │  • izlenmeyi ne belirlediğinin analizi
           │  • bugünün hedef yayın saati
           └─ 5 fikir + [1][2][3][4][5] [🔄]

sen basarsın ─ Telegram listener (5 dakikada bir bakar)
               │
               ├─ prompt yazılır (LLM)
               ├─ video üretilir (WaveSpeed)
               ├─ abone-ol bindirilir + 1080x1920 upscale (ffmpeg)
               ├─ YouTube'a GİZLİ yüklenir
               └─ hedef saate kuyruğa alınır

hedef saat ─── Publish at slot (15 dakikada bir bakar)
               └─ tam o saniyede herkese açık olur, Telegram'a link düşer
```

## Komutlar

Telegram'da bota yazabilirsin:

- `/fikir` — sabahı beklemeden 5 yeni fikir
- `/durum` — yayın kuyruğunda ne var

## Maliyet

| Kalem | Günlük |
|---|---|
| GitHub Actions | 0 (public repo sınırsız, private'ta ayda 2000 dk ücretsiz) |
| LLM (OpenRouter) | birkaç sent |
| WaveSpeed | kullandığın modelin 30 sn / 480p fiyatı |
| YouTube API | 0 (günlük 10.000 birim kotanın çok altında) |

Depoyu **private** yaparsan Actions dakikaları ücretsiz kotadan düşer. Günde
~20 dakika kullanır, aylık 2000 dakikalık ücretsiz kotanın içinde kalır.
