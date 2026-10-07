import os
import threading
import discord
from discord.ext import commands
from discord import app_commands, ButtonStyle, TextStyle
from discord.ui import Button, View, Modal, TextInput
from flask import Flask
from curl_cffi import requests as cffi_requests
import requests
import json

# ---------------------------------------------------------
# 1. FLASK KEEP-ALIVE
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
# 2. BOT AYARLARI
# ---------------------------------------------------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------------------------------------------
# 3. VERİ FORMATLAMA
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
# 4. MODAL
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
            # --- Discord ID Sorgu (requests kullanılıyor, curl_cffi değil) ---
            if self.param_type == "discord_id":
                url = f"https://discordlookup.mesavirep.xyz/v1/user/{val}"
                resp = requests.get(url, timeout=20)
                if resp.status_code == 200:
                    content = format_data(resp.json())
                else:
                    content = f"⚠️ API Hatası: {resp.status_code}"
            
            # --- IP Sorgu (VPN/Proxy Tespiti) ---
            elif self.param_type == "ip":
                url = f"http://ip-api.com/json/{val}?fields=status,message,country,regionName,city,isp,org,as,proxy,hosting,query"
                resp = requests.get(url, timeout=20)
                if resp.status_code == 200:
                    content = format_data(resp.json())
                else:
                    content = f"⚠️ API Hatası: {resp.status_code}"

            # --- E-posta İhlal Sorgusu ---
            elif self.param_type == "email_breach":
                url = f"https://api.xposedornot.com/v1/check-email/{val}"
                resp = requests.get(url, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    breaches = data.get("breaches", [])
                    if breaches:
                        content = f"**{val}** adresi şu ihlallerde bulundu:\n\n" + "\n".join([f"• {b}" for b in breaches])
                    else:
                        content = f"✅ **{val}** hiçbir bilinen ihlalde bulunamadı."
                elif resp.status_code == 404:
                    content = f"✅ **{val}** hiçbir bilinen ihlalde bulunamadı."
                else:
                    content = f"⚠️ API Hatası: {resp.status_code}"

            # --- Telefon Numarası Sorgusu ---
            elif self.param_type == "phone":
                url = f"https://api.apify.com/v2/acts/phoneinfoga~phone-number-osint-scanner/run-sync-get-dataset-items?token=FREE_TOKEN&phone={val}"
                resp = requests.get(url, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        content = format_data(data[0])
                    else:
                        content = "❌ Sonuç bulunamadı."
                else:
                    content = f"⚠️ API Hatası: {resp.status_code}"

            # --- Kullanıcı Adı Sorgusu ---
            elif self.param_type == "username":
                url = f"https://api.osint-web-mcp.com/search?username={val}"
                resp = requests.get(url, timeout=20)
                if resp.status_code == 200:
                    content = format_data(resp.json())
                else:
                    content = f"⚠️ API Hatası: {resp.status_code}"

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
# 5. BUTONLAR
# ---------------------------------------------------------
class SorguPaneliView(View):
    def __init__(self):
        super().__init__(timeout=None)

        # Discord ID
        btn_dc_id = Button(label="Discord ID", style=ButtonStyle.primary, row=0, custom_id="btn_dc_id")
        btn_dc_id.callback = lambda i: self.open_modal(i, "Discord ID Sorgu", "Discord ID", "discord_id")
        self.add_item(btn_dc_id)

        # IP Sorgu
        btn_ip = Button(label="IP Sorgu", style=ButtonStyle.primary, row=0, custom_id="btn_ip")
        btn_ip.callback = lambda i: self.open_modal(i, "IP Sorgu", "IP Adresi", "ip")
        self.add_item(btn_ip)

        # E-posta İhlal
        btn_email = Button(label="E-posta İhlal", style=ButtonStyle.primary, row=0, custom_id="btn_email")
        btn_email.callback = lambda i: self.open_modal(i, "E-posta İhlal Sorgu", "E-posta Adresi", "email_breach")
        self.add_item(btn_email)

        # Telefon Numarası Sorgu
        btn_phone = Button(label="Telefon Sorgu", style=ButtonStyle.success, row=1, custom_id="btn_phone")
        btn_phone.callback = lambda i: self.open_modal(i, "Telefon Numarası Sorgu", "Telefon Numarası (Uluslararası Format)", "phone")
        self.add_item(btn_phone)

        # Kullanıcı Adı Sorgu
        btn_username = Button(label="Kullanıcı Adı Sorgu", style=ButtonStyle.success, row=1, custom_id="btn_username")
        btn_username.callback = lambda i: self.open_modal(i, "Kullanıcı Adı Sorgu", "Kullanıcı Adı", "username")
        self.add_item(btn_username)

    async def open_modal(self, interaction: discord.Interaction, title: str, label: str, param_type: str):
        modal = SorguModal(title_name=title, label_name=label, param_type=param_type)
        await interaction.response.send_modal(modal)

# ---------------------------------------------------------
# 6. KOMUTLAR
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
