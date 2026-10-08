import os
import threading
import time
import discord
from discord.ext import commands
from discord import app_commands, ButtonStyle, TextStyle
from discord.ui import Button, View, Modal, TextInput
from flask import Flask
import aiohttp
import ssl
import json
import requests

# ---------------------------------------------------------
# 1. FLASK KEEP-ALIVE + SELF-PING
# ---------------------------------------------------------
app = Flask('')

@app.route('/')
def home():
    return "Sorgu Botu 7/24 Aktif!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def self_ping():
    """Botun kendi kendine ping atması için (Render uyumasın diye)."""
    # Render'ın sana verdiği URL'yi buraya yaz (sonunda / olmadan)
    # Örnek: "https://alves-bot.onrender.com"
    url = os.environ.get("RENDER_EXTERNAL_URL", "")
    if not url:
        # Render otomatik olarak RENDER_EXTERNAL_URL ortam değişkenini sağlar
        print("[Self-Ping] RENDER_EXTERNAL_URL bulunamadı, self-ping devre dışı.")
        return
    
    while True:
        try:
            time.sleep(240)  # 4 dakika bekle (Render 15 dk'da uyutur)
            r = requests.get(url, timeout=10)
            print(f"[Self-Ping] {url} -> {r.status_code}")
        except Exception as e:
            print(f"[Self-Ping] Hata: {e}")

def keep_alive():
    t1 = threading.Thread(target=run_flask)
    t1.daemon = True
    t1.start()
    
    t2 = threading.Thread(target=self_ping)
    t2.daemon = True
    t2.start()

# ---------------------------------------------------------
# 2. BOT AYARLARI
# ---------------------------------------------------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------------------------------------------
# 3. SSL CONTEXT
# ---------------------------------------------------------
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# ---------------------------------------------------------
# 4. VERİ FORMATLAMA
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
# 5. MODAL
# ---------------------------------------------------------
class SorguModal(Modal):
    def __init__(self, title_name: str, label_name: str, param_type: str):
        super().__init__(title=title_name)
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
        content = ""

        try:
            async with aiohttp.ClientSession() as session:
                # --- Discord ID Sorgu ---
                if self.param_type == "discord_id":
                    token = os.environ.get("DISCORD_BOT_TOKEN", "")
                    if not token:
                        content = "❌ Bot token'ı ayarlanmamış."
                    else:
                        url = f"https://discord.com/api/v10/users/{val}"
                        headers = {"Authorization": f"Bot {token}"}
                        async with session.get(url, headers=headers, ssl=ssl_context, timeout=20) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                filtered = {
                                    "ID": data.get("id"),
                                    "Kullanıcı Adı": data.get("username"),
                                    "Ayırıcı": data.get("discriminator"),
                                    "Global Ad": data.get("global_name"),
                                    "Bot mu": data.get("bot"),
                                    "Avatar Hash": data.get("avatar")
                                }
                                content = format_data(filtered)
                            else:
                                content = f"⚠️ API Hatası: {resp.status}"

                # --- IP Sorgu ---
                elif self.param_type == "ip":
                    url = f"http://ip-api.com/json/{val}?fields=status,message,country,regionName,city,isp,org,as,proxy,hosting,query"
                    async with session.get(url, ssl=ssl_context, timeout=20) as resp:
                        if resp.status == 200:
                            content = format_data(await resp.json())
                        else:
                            content = f"⚠️ API Hatası: {resp.status}"

                # --- E-posta İhlal ---
                elif self.param_type == "email_breach":
                    url = f"https://api.xposedornot.com/v1/check-email/{val}"
                    async with session.get(url, ssl=ssl_context, timeout=20) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            breaches = data.get("breaches", [])
                            if breaches:
                                content = f"**{val}** adresi şu ihlallerde bulundu:\n\n" + "\n".join([f"• {b}" for b in breaches])
                            else:
                                content = f"✅ **{val}** hiçbir bilinen ihlalde bulunamadı."
                        elif resp.status == 404:
                            content = f"✅ **{val}** hiçbir bilinen ihlalde bulunamadı."
                        else:
                            content = f"⚠️ API Hatası: {resp.status}"

                # --- Telefon Sorgu (PhoneInfoga - Apify) ---
                elif self.param_type == "phone":
                    token = os.environ.get("APIFY_TOKEN", "")
                    if not token:
                        content = "❌ Apify token'ı ayarlanmamış."
                    else:
                        url = f"https://api.apify.com/v2/acts/phoneinfoga~phone-number-osint-scanner/run-sync-get-dataset-items?token={token}&phone={val}"
                        async with session.get(url, ssl=ssl_context, timeout=60) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data:
                                    content = format_data(data[0])
                                else:
                                    content = "❌ Sonuç bulunamadı."
                            else:
                                content = f"⚠️ API Hatası: {resp.status}"

                # --- Kullanıcı Adı Sorgu (Sherlock) ---
                elif self.param_type == "username":
                    url = f"https://sherlock.nuro.dev/{val}"
                    headers = {"Accept": "application/json"}
                    async with session.get(url, headers=headers, ssl=ssl_context, timeout=30) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            found = {}
                            raw_data = data.get("data", data)
                            if isinstance(raw_data, dict):
                                for site, info in raw_data.items():
                                    if isinstance(info, dict):
                                        status = info.get("status", "")
                                        if status in ("found", "Claimed"):
                                            found[site] = info.get("url", info.get("url_main", ""))
                            if found:
                                content = f"**{val}** kullanıcı adı şu platformlarda bulundu:\n\n"
                                content += "\n".join([f"• **{site}:** {url}" for site, url in list(found.items())[:30]])
                                if len(found) > 30:
                                    content += f"\n\n*(Toplam {len(found)} sonuç, ilk 30 gösteriliyor)*"
                            else:
                                content = f"❌ **{val}** kullanıcı adı hiçbir platformda bulunamadı."
                        else:
                            content = f"⚠️ API Hatası: {resp.status}"

                # --- İl/İlçe Sorgu ---
                elif self.param_type == "city_district":
                    url = "https://furkandlkdr.github.io/mermis-turkiye-districts/turkey_cities_districts.json"
                    async with session.get(url, ssl=ssl_context, timeout=20) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            aranan = val.lower().strip()
                            bulundu = None
                            for key, info in data.items():
                                if isinstance(info, dict):
                                    province = info.get("province", "")
                                    if province.lower() == aranan:
                                        bulundu = info
                                        break
                            if bulundu:
                                province = bulundu.get("province", "")
                                districts = bulundu.get("districts", [])
                                ilceler = [d.get("name", "") for d in districts if isinstance(d, dict)]
                                content = f"📍 **{province}** ili ilçeleri:\n\n"
                                content += "\n".join([f"• {ilce}" for ilce in ilceler])
                                content += f"\n\n**Toplam:** {len(ilceler)} ilçe"
                            else:
                                content = f"❌ **{val}** adında bir il bulunamadı."
                        else:
                            content = f"⚠️ API Hatası: {resp.status}"

        except Exception as e:
            content = f"❌ Hata: `{str(e)}`"

        embed = discord.Embed(
            title=f"📋 {self.title} Sonucu",
            description=content[:4000],
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Sorgulayan: {interaction.user.name} • Sadece size özel görünür.")
        await interaction.followup.send(embed=embed, ephemeral=True)

# ---------------------------------------------------------
# 6. BUTONLAR
# ---------------------------------------------------------
class SorguPaneliView(View):
    def __init__(self):
        super().__init__(timeout=None)

        btn_dc_id = Button(label="Discord ID", style=ButtonStyle.primary, row=0, custom_id="btn_dc_id")
        btn_dc_id.callback = lambda i: self.open_modal(i, "Discord ID Sorgu", "Discord ID", "discord_id")
        self.add_item(btn_dc_id)

        btn_ip = Button(label="IP Sorgu", style=ButtonStyle.primary, row=0, custom_id="btn_ip")
        btn_ip.callback = lambda i: self.open_modal(i, "IP Sorgu", "IP Adresi", "ip")
        self.add_item(btn_ip)

        btn_email = Button(label="E-posta İhlal", style=ButtonStyle.primary, row=0, custom_id="btn_email")
        btn_email.callback = lambda i: self.open_modal(i, "E-posta İhlal Sorgu", "E-posta Adresi", "email_breach")
        self.add_item(btn_email)

        btn_phone = Button(label="Telefon Sorgu", style=ButtonStyle.success, row=1, custom_id="btn_phone")
        btn_phone.callback = lambda i: self.open_modal(i, "Telefon Numarası Sorgu", "Telefon Numarası (+12128148373 gibi)", "phone")
        self.add_item(btn_phone)

        btn_username = Button(label="Kullanıcı Adı Sorgu", style=ButtonStyle.success, row=1, custom_id="btn_username")
        btn_username.callback = lambda i: self.open_modal(i, "Kullanıcı Adı Sorgu", "Kullanıcı Adı", "username")
        self.add_item(btn_username)

        btn_city = Button(label="İl/İlçe Sorgu", style=ButtonStyle.success, row=1, custom_id="btn_city")
        btn_city.callback = lambda i: self.open_modal(i, "İl/İlçe Sorgu", "İl Adı (Örn: İstanbul)", "city_district")
        self.add_item(btn_city)

    async def open_modal(self, interaction: discord.Interaction, title: str, label: str, param_type: str):
        modal = SorguModal(title_name=title, label_name=label, param_type=param_type)
        await interaction.response.send_modal(modal)

# ---------------------------------------------------------
# 7. KOMUTLAR
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
    TOKEN = os.environ.get("DISCORD_BOT_TOKEN") or "DISCORD_BOT_TOKEN_BURAYA"
    bot.run(TOKEN)
