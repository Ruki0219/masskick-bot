import discord
from discord.ext import commands
from datetime import datetime
import re

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

DATE_FORMATS = ["%Y-%m-%d", "%B %d", "%b %d", "%d %B %Y", "%d %b %Y"]

def parse_date(text):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=None)
        except:
            continue
    return None

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

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

@bot.command()
async def masskick(ctx, *, args):
    # Parse role
    role_match = re.search(r'role:\s*<@&(\d+)>', args)
    if not role_match:
        await ctx.send("❌ Please mention a valid role using `role: @Role`.")
        return
    role_id = int(role_match.group(1))
    role = ctx.guild.get_role(role_id)
    if not role:
        await ctx.send("❌ Could not find the specified role.")
        return

    # Parse date and condition
    date_type = None
    date = None
    for condition in ["before", "after", "on"]:
        match = re.search(rf'{condition}:\s*([^\n\r]+)', args)
        if match:
            date = parse_date(match.group(1).strip())
            date_type = condition
            break

    if not date:
        await ctx.send("❌ Please provide a valid date using `before:`, `after:`, or `on:`.")
        return

    # Filter members
    matching_members = []
    for member in ctx.guild.members:
        if role in member.roles and not member.bot:
            joined = member.joined_at.replace(tzinfo=None)
            if (
                (date_type == "before" and joined < date) or
                (date_type == "after" and joined > date) or
                (date_type == "on" and joined.date() == date.date())
            ):
                matching_members.append(member)

    if not matching_members:
        await ctx.send("✅ No matching members found for that role and date filter.")
        return

    preview_list = "\n".join([f"{member.name} (joined: {member.joined_at.date()})" for member in matching_members[:15]])
    if len(matching_members) > 15:
        preview_list += f"\n...and {len(matching_members) - 15} more."

    confirm_msg = await ctx.send(
        f"⚠️ Are you sure you want to kick **{len(matching_members)}** members with the role {role.mention} who joined **{date_type} {date.date()}**?\n"
        f"Preview:\n```\n{preview_list}\n```\nReact with ✅ to confirm or ❌ to cancel."
    )
    await confirm_msg.add_reaction("✅")
    await confirm_msg.add_reaction("❌")

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_msg.id

    try:
        reaction, _ = await bot.wait_for("reaction_add", timeout=30.0, check=check)
    except:
        await ctx.send("❌ Timed out. No action taken.")
        return

    if str(reaction.emoji) == "❌":
        await ctx.send("❌ Cancelled.")
        return

    count = 0
    for member in matching_members:
        try:
            await member.kick(reason=f"Masskick by {ctx.author} using bot")
            count += 1
        except:
            pass

    await ctx.send(f"✅ Kicked {count}/{len(matching_members)} members.")

bot.run('DISCORD_TOKEN')
