import discord
from discord.ext import commands
import os
from datetime import datetime

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

# Disable default help command so we can define our own custom ones
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

TOKEN = os.getenv('DISCORD_TOKEN')

@bot.event
async def on_ready():
    print(f'✅ Bot is ready. Logged in as {bot.user.name}')

@bot.command(name='phelp')
async def phelp(ctx):
    help_text = """
**MassKick Bot Commands**
`!phelp` – Show this help message  
`!masskick role:@RoleName` – Kicks all users with that role  
`!masskick role:@RoleName before:YYYY-MM-DD` – Kicks users with that role who joined before that date  
`!masskick role:@RoleName after:YYYY-MM-DD` – Kicks users who joined after that date  
`!masskick role:@RoleName on:YYYY-MM-DD` – Kicks users who joined on that date  

✅ Example:
`!masskick role:@Newbie before:2025-08-01`
"""
    await ctx.send(help_text)

@bot.command()
@commands.has_permissions(administrator=True)
async def masskick(ctx, *, args):
    guild = ctx.guild
    params = args.lower().split()

    role = None
    date_filter = None
    filter_type = None

    for i, param in enumerate(params):
        if param.startswith("role:"):
            role_name = args[args.lower().find("role:") + 5:].split(" ")[0].strip()
            role = discord.utils.get(guild.roles, name=role_name) or discord.utils.get(ctx.message.role_mentions)
        elif param.startswith("before:"):
            filter_type = "before"
            date_filter = params[i].replace("before:", "")
        elif param.startswith("after:"):
            filter_type = "after"
            date_filter = params[i].replace("after:", "")
        elif param.startswith("on:"):
            filter_type = "on"
            date_filter = params[i].replace("on:", "")

    if not role:
        await ctx.send("⚠️ Could not find that role.")
        return
    if not date_filter:
        await ctx.send("⚠️ You need to specify a date filter using `before:`, `after:` or `on:`.")
        return

    try:
        target_date = datetime.strptime(date_filter, "%Y-%m-%d")
    except ValueError:
        await ctx.send("⚠️ Invalid date format. Use YYYY-MM-DD.")
        return

    kicked = 0
    failed = 0
    for member in guild.members:
        if role in member.roles:
            joined_at = member.joined_at
            if not joined_at:
                continue

            should_kick = (
                (filter_type == "before" and joined_at < target_date) or
                (filter_type == "after" and joined_at > target_date) or
                (filter_type == "on" and joined_at.date() == target_date.date())
            )

            if should_kick:
                try:
                    await member.kick(reason=f"Masskick by {ctx.author}")
                    kicked += 1
                except:
                    failed += 1

    await ctx.send(f"✅ Kicked {kicked} member(s) with role {role.name} using `{filter_type}: {date_filter}`.\n❌ Failed to kick {failed}.")

@masskick.error
async def masskick_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 You don’t have permission to use this command.")
    else:
        await ctx.send("⚠️ Error while processing command.")

bot.run(TOKEN)
