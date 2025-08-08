import discord
from discord.ext import commands
from discord.ext.commands import CommandRegistrationError
from discord.utils import get
import asyncio
from datetime import datetime
import re
import os

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Prevent help command conflict
try:
    bot.remove_command("help")
except CommandRegistrationError:
    pass

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

def parse_date(date_str):
    formats = ['%Y-%m-%d', '%d-%m-%Y', '%B %d, %Y', '%B %d', '%d %B %Y']
    for fmt in formats:
        try:
            result = datetime.strptime(date_str, fmt)
            if result.year == 1900:  # No year provided, use current
                result = result.replace(year=datetime.utcnow().year)
            return result
        except ValueError:
            continue
    return None

@bot.command(name="masskick")
@commands.has_permissions(kick_members=True)
async def masskick(ctx, *, args=None):
    import re
    from datetime import datetime

    # No args → show usage
    if not args:
        await ctx.send(
            "❌ Missing arguments.\n"
            "Usage: `!masskick @Role [before:YYYY-MM-DD | after:YYYY-MM-DD | on:YYYY-MM-DD]`\n"
            "Example: `!masskick @Visitors before:2025-08-08`"
        )
        return

    # Extract role mention or role:Name
    role_match = re.search(r"<@&(\d+)>|role:\s*([^\s]+)", args)
    if not role_match:
        await ctx.send(
            "❌ Please mention a role or use `role:RoleName`.\n"
            "Example: `!masskick @Visitors before:2025-08-08`"
        )
        return

    role_id = role_match.group(1)
    role_name = role_match.group(2)
    role = None

    if role_id:
        role = ctx.guild.get_role(int(role_id))
    elif role_name:
        role = discord.utils.find(lambda r: r.name.lower() == role_name.lower(), ctx.guild.roles)

    if not role:
        await ctx.send("❌ Role not found.")
        return

    # Extract and validate date filter
    date_filter = None
    date_type = None
    date_match = re.search(r"(before|after|on):\s*([^\s]+)", args)
    if date_match:
        date_type = date_match.group(1).lower()
        date_str = date_match.group(2)

        # Strict YYYY-MM-DD format check
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            await ctx.send(
                f"❌ Invalid date format `{date_str}`.\n"
                "Please use **YYYY-MM-DD**.\n"
                "Example: `!masskick @Visitors before:2025-08-08`"
            )
            return

        try:
            date_filter = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            await ctx.send(
                f"❌ Invalid date `{date_str}`.\n"
                "Please ensure the date exists and use **YYYY-MM-DD** format.\n"
                "Example: `!masskick @Visitors before:2025-08-08`"
            )
            return

    # Find members matching role (and date if provided)
    members_to_kick = []
    for member in role.members:
        if member.bot:
            continue
        if date_filter:
            joined_at = member.joined_at.replace(tzinfo=None)
            if date_type == "before" and joined_at >= date_filter:
                continue
            if date_type == "after" and joined_at <= date_filter:
                continue
            if date_type == "on" and joined_at.date() != date_filter.date():
                continue
        members_to_kick.append(member)

    if not members_to_kick:
        await ctx.send("❌ No members found matching that criteria.")
        return

    # Confirmation message
    member_list_str = "\n".join([f"{m} (Joined: {m.joined_at.date()})" for m in members_to_kick])
    preview_msg = f"**You are about to kick {len(members_to_kick)} members with the role `{role.name}`**"
    if date_filter:
        preview_msg += f" ({date_type}: {date_filter.date()})"
    preview_msg += f"\n```\n{member_list_str}\n```"
    preview_msg += "\nType `yes` to confirm, `no` to cancel."

    await ctx.send(preview_msg)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["yes", "no"]

    try:
        confirm = await bot.wait_for("message", check=check, timeout=30)
    except asyncio.TimeoutError:
        await ctx.send("⏳ Confirmation timed out. Cancelled.")
        return

    if confirm.content.lower() != "yes":
        await ctx.send("❌ Cancelled.")
        return

    # Kick members
    kicked_count = 0
    failed = []
    for member in members_to_kick:
        try:
            await member.kick(reason="Mass kick command")
            kicked_count += 1
        except Exception:
            failed.append(str(member))

    # Final result
    result_msg = f"✅ Kicked {kicked_count}/{len(members_to_kick)} members."
    if failed:
        result_msg += f"\n⚠️ Failed to kick {len(failed)} members:\n```\n" + "\n".join(failed) + "\n```"
    await ctx.send(result_msg)

@bot.command()
async def phelp(ctx):
    help_msg = (
        "```"
        "Mass Kick Command Help\n"
        "\n"
        "Usage:\n"
        "!masskick role:@RoleName [before:YYYY-MM-DD] [after:YYYY-MM-DD] [on:YYYY-MM-DD]\n"
        "\n"
        "Examples:\n"
        "!masskick role:@Newbie before:2025-08-01\n"
        "!masskick role:@Trial after:2025-07-01\n"
        "!masskick role:@Raiders on:2025-08-01\n"
        "\n"
        "Notes:\n"
        "- Dates must be in YYYY-MM-DD format.\n"
        "- At least a role mention is required.\n"
        "- Date filters are optional, but only one type can be used per command.\n"
        "- Bot will ask for confirmation before kicking.\n"
        "```"
    )
    await ctx.send(help_msg)

# Optional: replace this with your secret setup for Render
import os
bot.run(os.environ["DISCORD_TOKEN"])
bot.run(TOKEN)
