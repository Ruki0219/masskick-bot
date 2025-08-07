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

@bot.command()
@commands.has_permissions(kick_members=True)
async def masskick(ctx, *, args):
    arg_pattern = r'(\w+):\s*([^\n]+)'
    matches = dict(re.findall(arg_pattern, args))

    role_mention = matches.get("role")
    before = matches.get("before")
    after = matches.get("after")
    on = matches.get("on")

    if not role_mention:
        await ctx.send("❌ Please provide a role.")
        return

    # Resolve role from mention or name
    role_id_match = re.search(r'<@&(\d+)>', role_mention)
    role = None
    if role_id_match:
        role_id = int(role_id_match.group(1))
        role = ctx.guild.get_role(role_id)
    else:
        role = get(ctx.guild.roles, name=role_mention.strip())

    if not role:
        await ctx.send("❌ Role not found.")
        return

    # Parse date filters
    before_date = parse_date(before) if before else None
    after_date = parse_date(after) if after else None
    on_date = parse_date(on) if on else None

    if on_date:
        # Narrow range to one day
        after_date = on_date.replace(hour=0, minute=0, second=0)
        before_date = on_date.replace(hour=23, minute=59, second=59)

    # Build filtered member list
    matching_members = []
    async for member in ctx.guild.fetch_members(limit=None):
        if member.bot or role not in member.roles or not member.joined_at:
            continue
        joined = member.joined_at.replace(tzinfo=None)
        if before_date and joined >= before_date:
            continue
        if after_date and joined <= after_date:
            continue
        matching_members.append(member)

    if not matching_members:
        await ctx.send("✅ No matching members found.")
        return

    preview_list = '\n'.join(f"{m.name} (joined: {m.joined_at.strftime('%Y-%m-%d')})" for m in matching_members[:15])
    embed = discord.Embed(title="Mass Kick Confirmation", color=discord.Color.orange())
    if len(matching_members) > 15:
        embed.description = (
            f"⚠️ Are you sure you want to kick **{len(matching_members)}** members with the role {role.mention}?\n"
            f"Preview:\n```\n{preview_list}\n...and {len(matching_members) - 15} more.\n```"
        )
    else:
        embed.description = (
            f"⚠️ Are you sure you want to kick **{len(matching_members)}** members with the role {role.mention}?\n"
            f"Preview:\n```\n{preview_list}\n```"
        )

    message = await ctx.send(embed=embed)
    await message.add_reaction("✅")
    await message.add_reaction("❌")

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == message.id

    try:
        reaction, _ = await bot.wait_for("reaction_add", timeout=30.0, check=check)
        if str(reaction.emoji) == "❌":
            await ctx.send("❌ Mass kick canceled.")
            return
    except asyncio.TimeoutError:
        await ctx.send("⌛ Timed out. Mass kick canceled.")
        return

    # Proceed to kick
    kicked = 0
    failed = []

    for member in matching_members:
        try:
            await member.kick(reason="Mass kick command")
            kicked += 1
        except discord.Forbidden:
            failed.append(str(member))
        except Exception as e:
            failed.append(f"{member} ({e.__class__.__name__})")

    # Final summary
    summary_message = f"✅ Kicked **{kicked}/{len(matching_members)}** members."

    if failed:
        preview_failed = "\n".join(failed[:10])
        summary_message += f"\n⚠️ Failed to kick {len(failed)} members."
        summary_message += f"\n```\n{preview_failed}"
        if len(failed) > 10:
            summary_message += f"\n...and {len(failed) - 10} more."
        summary_message += "\n```"

    await ctx.send(summary_message)

@bot.command()
async def phelp(ctx):
    help_msg = (
        "**Commands:**\n"
        "`!masskick role: @Role before: YYYY-MM-DD`\n"
        "`!masskick role: @Role after: August 1`\n"
        "`!masskick role: @Role on: 2025-08-01`\n"
        "\n**Examples:**\n"
        "`!masskick role: @Newbie before: 2025-08-01`\n"
        "`!masskick role: @Trial after: August 1`\n"
        "`!masskick role: @Raiders on: 1 Aug 2025`\n"
        "\nSupports flexible date formats and will ask for confirmation before kicking."
    )
    await ctx.send(help_msg)

# Optional: replace this with your secret setup for Render
import os
bot.run(os.environ["DISCORD_TOKEN"])
bot.run(TOKEN)
