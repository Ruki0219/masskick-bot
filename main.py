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
    import asyncio
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
        if not member.joined_at:
            # skip members with missing joined_at
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

    # Build pages for preview (PAGE_SIZE per page)
    PAGE_SIZE = 15
    entries = [f"{m} (joined: {m.joined_at.date()})" for m in members_to_kick]
    pages = [entries[i:i + PAGE_SIZE] for i in range(0, len(entries), PAGE_SIZE)]
    total_pages = len(pages)
    current_page = 0

    # Helper to build embed for a page
    def build_confirm_embed(page_idx: int):
        embed = discord.Embed(
            title="⚠️ Mass Kick Confirmation",
            color=discord.Color.orange()
        )
        header = f"Are you sure you want to kick **{len(members_to_kick)}** members with the role {role.mention}?"
        if date_filter:
            header += f"\nFilter: **{date_type} {date_filter.date()}**"
        embed.description = header + "\n\n"
        page_entries = pages[page_idx]
        body = "\n".join(page_entries)
        embed.add_field(name="Preview", value=f"```{body}```", inline=False)
        embed.set_footer(text=f"Page {page_idx + 1}/{total_pages} • React ◀️ ▶️ to navigate • ✅ confirm • ❌ cancel")
        return embed

    # Send initial embed and add reactions
    confirm_message = await ctx.send(embed=build_confirm_embed(current_page))
    # Add reactions (left, right, confirm, cancel)
    emojis = ["◀️", "▶️", "✅", "❌"]
    for em in emojis:
        try:
            await confirm_message.add_reaction(em)
        except Exception:
            pass  # ignore if adding reaction fails

    # Reaction check: only command author, same message
    def reaction_check(reaction, user):
        return (
            user == ctx.author
            and reaction.message.id == confirm_message.id
            and str(reaction.emoji) in emojis
        )

    # Wait for interactions (paging + confirm/cancel)
    while True:
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=120.0, check=reaction_check)
        except asyncio.TimeoutError:
            try:
                await confirm_message.clear_reactions()
            except Exception:
                pass
            await ctx.send("⏳ Confirmation timed out. Cancelled.")
            return

        emoji = str(reaction.emoji)

        # remove the user's reaction to keep UI clean (if possible)
        try:
            await confirm_message.remove_reaction(reaction.emoji, user)
        except Exception:
            pass

        if emoji == "◀️":
            current_page = (current_page - 1) % total_pages
            try:
                await confirm_message.edit(embed=build_confirm_embed(current_page))
            except Exception:
                pass

        elif emoji == "▶️":
            current_page = (current_page + 1) % total_pages
            try:
                await confirm_message.edit(embed=build_confirm_embed(current_page))
            except Exception:
                pass

        elif emoji == "❌":
            try:
                await confirm_message.clear_reactions()
            except Exception:
                pass
            await ctx.send("❌ Mass kick canceled.")
            return

        elif emoji == "✅":
            # proceed to perform kicks
            try:
                await confirm_message.clear_reactions()
            except Exception:
                pass
            break

    # Before kicking, ensure the bot actually has kick permission
    if not ctx.guild.me.guild_permissions.kick_members:
        await ctx.send("❌ I don't have the `Kick Members` permission. Please grant it and try again.")
        return

    # Perform kicks (respecting rate limits)
    kicked_count = 0
    failed = []
    for member in members_to_kick:
        try:
            await member.kick(reason=f"Mass kick by {ctx.author}")
            kicked_count += 1
            await asyncio.sleep(1.0)  # safe delay to avoid hitting rate limits
        except discord.Forbidden:
            failed.append(f"{member} – missing permissions / role hierarchy")
        except Exception as e:
            failed.append(f"{member} – {e.__class__.__name__}")

    # Final result embed
    result_embed = discord.Embed(
        title="✅ Mass Kick Results",
        color=discord.Color.green()
    )
    result_embed.add_field(name="Summary", value=f"Kicked **{kicked_count}/{len(members_to_kick)}** members.", inline=False)
    if failed:
        # show up to first 25 failures to avoid huge message
        max_show = 25
        show_list = failed[:max_show]
        failed_text = "\n".join(show_list)
        if len(failed) > max_show:
            failed_text += f"\n...and {len(failed) - max_show} more."
        result_embed.add_field(name=f"Failed to kick {len(failed)} members", value=f"```{failed_text}```", inline=False)
        result_embed.color = discord.Color.orange()

    await ctx.send(embed=result_embed)

@bot.command()
async def phelp(ctx):
    embed = discord.Embed(
        title="📜 Mass Kick Command Help",
        description=(
            "**Usage:**\n"
            "`!masskick role:@RoleName [before:YYYY-MM-DD] [after:YYYY-MM-DD] [on:YYYY-MM-DD]`\n\n"
            "**Examples:**\n"
            "`!masskick role:@Newbie before:2025-08-01`\n"
            "`!masskick role:@Trial after:2025-07-01`\n"
            "`!masskick role:@Raiders on:2025-08-01`\n\n"
            "**Notes:**\n"
            "- Dates **must** be in `YYYY-MM-DD` format.\n"
            "- At least a **role mention** is required.\n"
            "- Only **one date filter** (`before`, `after`, or `on`) can be used per command.\n"
            "- Bot will ask for confirmation before kicking."
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="Pro tip: Use with caution — kicks are permanent!")

    await ctx.send(embed=embed)

# Optional: replace this with your secret setup for Render
import os
bot.run(os.environ["DISCORD_TOKEN"])
bot.run(TOKEN)
