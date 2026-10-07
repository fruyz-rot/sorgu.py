import os
import threading
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands, ButtonStyle, TextStyle
from discord.ui import Button, View, Modal, TextInput
from flask import Flask

# ---------------------------------------------------------
# 1. FLASK KEEP-ALIVE SERVER (Render 7/24 Aktiflik İçin)
# ---------------------------------------------------------
app = Flask('')

@app.route('/')
def home():
    return "Sorgu Botu 7/24 Aktif!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# ---------------------------------------------------------
# 2. DISCORD BOT AYARLARI
# ---------------------------------------------------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------------------------------------------
# 3. VERİ FORMATLAMA FONKSİYONU
# ---------------------------------------------------------
def format_data(obj, indent=0):
    lines = []
    prefix = "  " * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_clean = str(k).replace("_", " ").replace("-", " ").title()
            if isinstance(v, (dict, list)):
                lines.append(f"{prefix}🔹 **{key_clean}:**")
                lines.append(format_data(v, indent + 1))
            else:
                lines.append(f"{prefix}• **{key_clean}:** {v}")
    elif isinstance(obj, list):
        for idx, item in enumerate(obj, 1):
            lines.append(f"{prefix}📌 **Kayıt #{idx}**")
            lines.append(format_data(item, indent + 1))
    else:
        lines.append(f"{prefix}{obj}")
    return "\n".join(lines)

# ---------------------------------------------------------
# 4. MODAL (Giriş Kutusu & API Sorgusu)
# ---------------------------------------------------------
class SorguModal(Modal):
    def __init__(self, title_name: str, label_name: str, api_url: str, param_type: str):
        super().__init__(title=title_name)
        self.api_url = api_url
        self.param_type = param_type
        
        self.user_input = TextInput(
            label=label_name,
            placeholder=f"Lütfen {label_name.lower()} giriniz...",
            required=True,
            style=TextStyle.short
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        val = self.user_input.value.strip()
        
        if self.param_type == "ip":
            target_url = f"https://freegeoip.app/json/{val}"
        else:
            target_url = f"{self.api_url}{val}"

        # 403 Hatasını Önlemek İçin Chrome Tarayıcı Başlığı (User-Agent)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(target_url, timeout=15) as resp:
                    if resp.status == 200:
                        try:
                            data = await resp.json()
                            formatted_text = format_data(data)
                            
                            if not formatted_text.strip():
                                content = "❌ Sorgu tamamlandı fakat herhangi bir kayıt bulunamadı."
                            elif len(formatted_text) > 3900:
                                content = formatted_text[:3900] + "\n\n*(Sonuç çok uzun olduğu için kısaltıldı)*"
                            else:
                                content = formatted_text
                        except Exception:
                            text = await resp.text()
                            content = f"```\n{text[:1900]}\n```"
                    else:
                        content = f"⚠️ API İsteği Başarısız Oldu! Kod: {resp.status}"
        except Exception as e:
            content = f"❌ API bağlantısı sırasında hata oluştu:\n`{str(e)}`"

        embed = discord.Embed(
            title=f"📋 {self.title} Sonucu",
            description=content,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • Sadece size özel görünür.")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

# ---------------------------------------------------------
# 5. BUTON MENÜSÜ VE FARKLI SATIR RENKLERİ
# ---------------------------------------------------------
class SorguPaneliView(View):
    def __init__(self):
        super().__init__(timeout=None)

        # --- 1. SATIR: MAVİ BUTONLAR ---
        btn_dc_id = Button(label="Discord ID", style=ButtonStyle.primary, row=0, custom_id="btn_dc_id")
        btn_dc_id.callback = lambda i: self.open_modal(i, "Discord ID Sorgu", "Discord ID", "https://sanchez.tr/api/discord.php?id=", "id")
        self.add_item(btn_dc_id)

        btn_dc_mail = Button(label="Discord Mail", style=ButtonStyle.primary, row=0, custom_id="btn_dc_mail")
        btn_dc_mail.callback = lambda i: self.open_modal(i, "Discord Mail Sorgu", "E-Mail Adresi", "https://sanchez.tr/api/discord.php?mail=", "mail")
        self.add_item(btn_dc_mail)

        btn_iban = Button(label="IBAN Sorgu", style=ButtonStyle.primary, row=0, custom_id="btn_iban")
        btn_iban.callback = lambda i: self.open_modal(i, "Güncel IBAN Sorgu", "IBAN Numarası", "https://sanchez.tr/api/iban.php?iban=", "iban")
        self.add_item(btn_iban)

        btn_sms = Button(label="SMS Bomber", style=ButtonStyle.primary, row=0, custom_id="btn_sms")
        btn_sms.callback = lambda i: self.open_modal(i, "SMS Bomber", "Telefon Numarası (GSM)", "http://sanchez.tr/api/smsbomber.php?gsm=", "gsm")
        self.add_item(btn_sms)

        btn_ip = Button(label="IP Sorgu", style=ButtonStyle.primary, row=0, custom_id="btn_ip")
        btn_ip.callback = lambda i: self.open_modal(i, "IP Sorgu", "IP Adresi", "https://freegeoip.app/json/", "ip")
        self.add_item(btn_ip)

        # --- 2. SATIR: YEŞİL BUTONLAR ---
        btn_tc = Button(label="TC Sorgu", style=ButtonStyle.success, row=1, custom_id="btn_tc")
        btn_tc.callback = lambda i: self.open_modal(i, "TC Sorgu", "TC Kimlik No", "http://sanchez.tr/api/tc.php?tc=", "tc")
        self.add_item(btn_tc)

        btn_aile = Button(label="Aile Sorgu", style=ButtonStyle.success, row=1, custom_id="btn_aile")
        btn_aile.callback = lambda i: self.open_modal(i, "Aile Sorgu", "TC Kimlik No", "http://sanchez.tr/api/aile.php?tc=", "tc")
        self.add_item(btn_aile)

        btn_sulale = Button(label="Sülale Sorgu", style=ButtonStyle.success, row=1, custom_id="btn_sulale")
        btn_sulale.callback = lambda i: self.open_modal(i, "Sülale Sorgu", "TC Kimlik No", "https://sanchez.tr/api/sulale.php?tc=", "tc")
        self.add_item(btn_sulale)

        btn_cocuk = Button(label="Çocuk Sorgu", style=ButtonStyle.success, row=1, custom_id="btn_cocuk")
        btn_cocuk.callback = lambda i: self.open_modal(i, "Çocuk Sorgu", "TC Kimlik No", "http://sanchez.tr/api/cocuk.php?tc=", "tc")
        self.add_item(btn_cocuk)

        btn_adres = Button(label="Adres Sorgu", style=ButtonStyle.success, row=1, custom_id="btn_adres")
        btn_adres.callback = lambda i: self.open_modal(i, "Adres Sorgu", "TC Kimlik No", "http://sanchez.tr/api/adres.php?tc=", "tc")
        self.add_item(btn_adres)

        # --- 3. SATIR: KIRMIZI BUTONLAR ---
        btn_isyeri = Button(label="İşyeri Sorgu", style=ButtonStyle.danger, row=2, custom_id="btn_isyeri")
        btn_isyeri.callback = lambda i: self.open_modal(i, "İşyeri Sorgu", "TC Kimlik No", "http://sanchez.tr/api/isyeri.php?tc=", "tc")
        self.add_item(btn_isyeri)

        btn_gsmtc = Button(label="GSM -> TC", style=ButtonStyle.danger, row=2, custom_id="btn_gsmtc")
        btn_gsmtc.callback = lambda i: self.open_modal(i, "GSM'den TC Sorgu", "GSM / Telefon No", "http://sanchez.tr/api/gsmtc.php?gsm=", "gsm")
        self.add_item(btn_gsmtc)

        btn_tcgsm = Button(label="TC -> GSM", style=ButtonStyle.danger, row=2, custom_id="btn_tcgsm")
        btn_tcgsm.callback = lambda i: self.open_modal(i, "TC'den GSM Sorgu", "TC Kimlik No", "http://sanchez.tr/api/tcgsm.php?tc=", "tc")
        self.add_item(btn_tcgsm)

    async def open_modal(self, interaction: discord.Interaction, title: str, label: str, api_url: str, param_type: str):
        modal = SorguModal(title_name=title, label_name=label, api_url=api_url, param_type=param_type)
        await interaction.response.send_modal(modal)

# ---------------------------------------------------------
# 6. KOMUTLAR VE BAŞLATMA
# ---------------------------------------------------------
@bot.event
async def on_ready():
    print(f"[{bot.user}] Sistem aktif!")
    bot.add_view(SorguPaneliView())
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} slash komut eşitlendi.")
    except Exception as e:
        print(f"Komut eşitleme hatası: {e}")

@bot.tree.command(name="sorgula", description="Sorgu panelini kanala gönderir (Sadece Admin).")
@app_commands.checks.has_permissions(administrator=True)
async def sorgula(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔍 Gelişmiş Sorgu Paneli",
        description=(
            "Aşağıdaki butonları kullanarak sorgulama yapabilirsiniz.\n\n"
            "🔒 **Gizlilik:** Sorgu sonuçları **sadece sorguyu yapan kişiye** özel gösterilir."
        ),
        color=discord.Color.gold()
    )
    if interaction.guild and interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text="Sorgu Sistemi • 7/24 Aktif")

    await interaction.response.send_message(embed=embed, view=SorguPaneliView())

@sorgula.error
async def sorgula_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ **Bu komutu kullanmak için `Yönetici` yetkisine sahip olmalısınız!**",
            ephemeral=True
        )

if __name__ == "__main__":
    keep_alive()
    TOKEN = os.environ.get("DISCORD_TOKEN") or "DISCORD_BOT_TOKEN_BURAYA"
    bot.run(TOKEN)
