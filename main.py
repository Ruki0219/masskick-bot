import discord
from discord.ext import commands
import asyncio
import datetime
import json
import re
import os
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

MOD_ROLE_FILE = 'mod_roles.json'

# Load mod roles
def load_mod_roles():
    try:
        with open(MOD_ROLE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_mod_roles(data):
    with open(MOD_ROLE_FILE, 'w') as f:
        json.dump(data, f, indent=4)

mod_roles = load_mod_roles()

def is_mod(ctx):
    if ctx.author.guild_permissions.manage_guild:
        return True
    guild_id = str(ctx.guild.id)
    role_id = mod_roles.get(guild_id)
    if role_id:
        role = discord.utils.get(ctx.guild.roles, id=int(role_id))
        return role in ctx.author.roles
    return False

def parse_date(input_str):
    formats = [
        "%Y-%m-%d",
        "%m-%d-%y",
        "%m/%d",
        "%B %d",
        "%b %d",
        "%B %d, %Y",
        "%b %d, %Y"
    ]
    now = datetime.datetime.now()
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(input_str, fmt)
            if not dt.year or dt.year == 1900:
                dt = dt.replace(year=now.year)
            return dt
        except ValueError:
            continue
    return None

@bot.command(name='setupmod')
async def setupmod(ctx, role: discord.Role):
    if not ctx.author.guild_permissions.manage_guild:
        return await ctx.send("You must have 'Manage Server' permission to use this command.")
    mod_roles[str(ctx.guild.id)] = str(role.id)
    save_mod_roles(mod_roles)
    await ctx.send(f"✅ Mod role set to {role.mention}")

@bot.command(name='deletemod')
async def deletemod(ctx):
    if not ctx.author.guild_permissions.manage_guild:
        return await ctx.send("You must have 'Manage Server' permission to use this command.")
    if str(ctx.guild.id) in mod_roles:
        del mod_roles[str(ctx.guild.id)]
        save_mod_roles(mod_roles)
        await ctx.send("✅ Mod role restriction removed.")
    else:
        await ctx.send("No mod role was set.")

@bot.command(name='phelp')
async def phelp(ctx):
    help_text = (
        "**MassKick Bot Commands**\n"
        "`!setupmod @Role` — Set who can run commands\n"
        "`!deletemod` — Remove mod-only restriction\n"
        "`!masskick @RoleName` — Kick all users with that role\n"
        "`!masskick role:@RoleName before:July 4` — Kick users with that role who joined before the date\n"
        "`!masskick role:@RoleName on:2025-08-01` — Kick users who joined on that date\n"
        "`!masskick role:@RoleName after:07/04` — Kick users who joined after that date\n"
        "\n✅ Supported date formats: `2025-08-01`, `07-04-25`, `07/04`, `July 4`, `July 4, 2025`"
    )
    await ctx.send(help_text)

@bot.command()
async def masskick(ctx, *, args):
    if not is_mod(ctx):
        return await ctx.send("🚫 You don't have permission to use this command.")

    args = args.strip()

    if re.fullmatch(r'<@&\d+>|\d+', args):
        role_id = int(re.sub(r'\D', '', args))
        role = ctx.guild.get_role(role_id)
        date_type = None
        target_date = None
    elif re.fullmatch(r'@?\w+', args):
        role = discord.utils.get(ctx.guild.roles, name=args.replace('@', ''))
        date_type = None
        target_date = None
    else:
        role_match = re.search(r'role:(<@&\d+>|\d+|[^\s]+)', args)
        date_match = re.search(r'(before|after|on):([^\n]+)', args)

        if not role_match:
            return await ctx.send("❌ Invalid command. You must provide a role.")

        role_input = role_match.group(1).strip()
        if role_input.startswith("<@&"):
            role_id = int(re.sub(r'\D', '', role_input))
            role = ctx.guild.get_role(role_id)
        elif role_input.isdigit():
            role = ctx.guild.get_role(int(role_input))
        else:
            role = discord.utils.get(ctx.guild.roles, name=role_input)

        if not role:
            return await ctx.send("❌ Role not found.")

        if date_match:
            date_type = date_match.group(1).lower()
            date_str = date_match.group(2).strip()
            target_date = parse_date(date_str)

            if not target_date:
                return await ctx.send("❌ Invalid date format.")
        else:
            date_type = None
            target_date = None

    if not role:
        return await ctx.send("❌ Role not found.")

    members = [m for m in ctx.guild.members if role in m.roles and not m.bot]

    if date_type == "before":
        filtered = [m for m in members if m.joined_at and m.joined_at < target_date]
    elif date_type == "after":
        filtered = [m for m in members if m.joined_at and m.joined_at > target_date]
    elif date_type == "on":
        filtered = [m for m in members if m.joined_at and m.joined_at.date() == target_date.date()]
    else:
        filtered = members

    if not filtered:
        return await ctx.send("⚠️ No matching members found.")

    await ctx.send(f"⚠️ Found {len(filtered)} member(s) with role {role.mention}{f' who joined {date_type} {target_date.strftime('%Y-%m-%d')}' if date_type else ''}.\nType `YES` to confirm kicking them.")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for('message', timeout=30.0, check=check)
        if msg.content.strip().upper() != "YES":
            return await ctx.send("❌ Cancelled.")
    except asyncio.TimeoutError:
        return await ctx.send("⌛ No confirmation received. Cancelled.")

    count = 0
    for member in filtered:
        try:
            await member.kick(reason=f"Mass kick by {ctx.author} via bot")
            count += 1
            await asyncio.sleep(2)  # safe delay per user
        except Exception as e:
            await ctx.send(f"⚠️ Failed to kick {member.display_name}: {e}")

    await ctx.send(f"✅ Kicked {count} member(s). Done.")

bot.run('YOUR_BOT_TOKEN')
