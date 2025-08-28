import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "your_bot_token_here")
STAFF_CHANNEL_ID = int(os.getenv("STAFF_CHANNEL_ID", "1410225154239238184"))  # Hardcoded report channel ID

class DungeonKeeper(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        intents.dm_messages = True
        
        super().__init__(command_prefix='!', intents=intents)
        
        # In-memory storage
        self.cases: Dict[int, Dict] = {}  # case_id -> case_data
        self.user_xp: Dict[int, int] = {}  # user_id -> xp
        self.active_timers: Dict[int, Dict] = {}  # user_id -> timer_data
        self.pending_cases: Dict[int, bool] = {}  # user_id -> waiting for case description
        self.reminders: Dict[int, List[Dict]] = {}  # user_id -> list of reminders
        self.case_counter = 1
        
        # Load configuration and data
        self.load_data()

    def load_data(self):
        """Load study quotes and topics from JSON files"""
        try:
            with open('data/study_quotes.json', 'r') as f:
                self.study_quotes = json.load(f)
        except FileNotFoundError:
            self.study_quotes = [
                "The expert in anything was once a beginner.",
                "Success is the sum of small efforts repeated day in and day out.",
                "Don't watch the clock; do what it does. Keep going.",
                "The future depends on what you do today."
            ]
        
        try:
            with open('data/topics.json', 'r') as f:
                self.topics = json.load(f)
        except FileNotFoundError:
            self.topics = [
                "What's the most interesting thing you learned this week?",
                "If you could have dinner with any historical figure, who would it be?",
                "What's a skill you'd love to master?",
                "What motivates you to keep studying?"
            ]

    async def setup_hook(self):
        """Sync slash commands when bot starts"""
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f'{self.user} has logged in!')
        print(f'DungeonKeeper is online as {self.user}')
        
        # Set bot status to online
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for support requests"
            )
        )
        
        # Start reminder task
        self.check_reminders.start()

    async def on_message(self, message):
        """Handle DM messages for staff support"""
        if message.author == self.user:
            return
        
        if isinstance(message.channel, discord.DMChannel):
            await self.handle_dm_message(message)
        
        await self.process_commands(message)

    async def handle_dm_message(self, message):
        """Handle DM messages with interactive support system"""
        user_id = message.author.id
        
        # Check if user is already in a support flow
        if user_id in self.pending_cases:
            await self.process_support_case(message)
        else:
            await self.start_support_flow(message)

    async def start_support_flow(self, message):
        """Start the interactive support flow"""
        embed = discord.Embed(
            title="🎯 DungeonKeeper Support System",
            description="Welcome! I'm here to help you with any questions or issues.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📝 How it works:",
            value="• Describe your issue or question\n• Our staff team will be notified\n• You'll get a response as soon as possible\n• All conversations are tracked with a case ID",
            inline=False
        )
        
        embed.add_field(
            name="🔍 What to include:",
            value="• Clear description of your issue\n• Any error messages you're seeing\n• Steps you've already tried\n• Screenshots if helpful",
            inline=False
        )
        
        embed.set_footer(text="Ready to start? Click the button below!")
        
        # Create proceed button
        view = SupportStartView(self)
        await message.author.send(embed=embed, view=view)

    async def process_support_case(self, message):
        """Process the actual support case after user clicks proceed"""
        user_id = message.author.id
        
        # Use hardcoded staff channel ID
        staff_channel = self.get_channel(STAFF_CHANNEL_ID)
        if not staff_channel:
            logger.error(f"Staff channel {STAFF_CHANNEL_ID} not found")
            await message.author.send("❌ Unable to reach staff team. Please try again later.")
            return
        
        # Create case
        case_id = self.case_counter
        self.case_counter += 1
        
        # Create embed for staff channel
        embed = discord.Embed(
            title=f"🆘 New Support Case #{case_id}",
            description=message.content,
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        
        embed.set_author(
            name=f"{message.author.display_name} ({message.author.id})",
            icon_url=message.author.avatar.url if message.author.avatar else None
        )
        
        # Handle attachments
        if message.attachments:
            attachment_urls = [att.url for att in message.attachments]
            embed.add_field(
                name="📎 Attachments",
                value="\n".join(attachment_urls),
                inline=False
            )
        
        # Send to staff channel with @everyone ping and create thread
        staff_message = await staff_channel.send("@everyone", embed=embed)
        thread = await staff_message.create_thread(
            name=f"Case #{case_id} - {message.author.display_name}",
            auto_archive_duration=1440  # 24 hours
        )
        
        # Store case data
        self.cases[case_id] = {
            'user_id': message.author.id,
            'thread_id': thread.id,
            'created_at': datetime.utcnow(),
            'status': 'open'
        }
        
        # Remove from pending
        del self.pending_cases[user_id]
        
        # Confirm to user
        confirm_embed = discord.Embed(
            title="✅ Support Case Created",
            description=f"Your case has been submitted successfully!\n\n**Case ID:** #{case_id}\n**Status:** Open\n\nOur staff team has been notified and will respond as soon as possible.",
            color=discord.Color.green()
        )
        confirm_embed.set_footer(text="You'll receive updates about your case here in DMs")
        await message.author.send(embed=confirm_embed)

    @tasks.loop(minutes=1)
    async def check_reminders(self):
        """Check and send reminders"""
        current_time = datetime.utcnow()
        
        for user_id, reminders in list(self.reminders.items()):
            for reminder in list(reminders):
                if current_time >= reminder['time']:
                    user = self.get_user(user_id)
                    if user:
                        try:
                            embed = discord.Embed(
                                title="⏰ Reminder",
                                description=reminder['message'],
                                color=discord.Color.blue(),
                                timestamp=current_time
                            )
                            embed.set_footer(text=f"Set {reminder['set_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
                            await user.send(embed=embed)
                        except discord.Forbidden:
                            pass
                    
                    reminders.remove(reminder)
            
            if not reminders:
                del self.reminders[user_id]

# Support System UI Components
class SupportStartView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)  # 5 minute timeout
        self.bot = bot

    @discord.ui.button(label="📝 Start Support Request", style=discord.ButtonStyle.primary, emoji="🚀")
    async def start_support(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Mark user as ready to submit their case
        self.bot.pending_cases[interaction.user.id] = True
        
        embed = discord.Embed(
            title="📝 Ready to Help!",
            description="Perfect! Now please describe your issue or question in detail.\n\nI'll forward it to our staff team right away.",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="💡 Tips for better support:",
            value="• Be specific about the problem\n• Include any error messages\n• Mention what you were trying to do\n• Add screenshots if helpful",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_support(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="✋ Support Cancelled",
            description="No problem! If you need help later, just send me another message.",
            color=discord.Color.light_grey()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

bot = DungeonKeeper()

# Staff Support Commands
@bot.tree.command(name="reply", description="Reply to a support case")
@discord.app_commands.describe(
    case="Case ID to reply to",
    message="Message to send to the user"
)
async def reply_case(interaction: discord.Interaction, case: int, message: str):
    """Reply to a support case"""
    if case not in bot.cases:
        await interaction.response.send_message("Case not found.", ephemeral=True)
        return
    
    case_data = bot.cases[case]
    user = bot.get_user(case_data['user_id'])
    
    if not user:
        await interaction.response.send_message("User not found.", ephemeral=True)
        return
    
    try:
        embed = discord.Embed(
            title=f"Staff Response - Case #{case}",
            description=message,
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Replied by {interaction.user.display_name}")
        
        await user.send(embed=embed)
        await interaction.response.send_message(f"Reply sent to user for case #{case}", ephemeral=True)
        
        # Log in thread
        thread = bot.get_channel(case_data['thread_id'])
        if thread:
            await thread.send(f"**Reply sent by {interaction.user.mention}:**\n{message}")
    
    except discord.Forbidden:
        await interaction.response.send_message("Could not send DM to user. They may have DMs disabled.", ephemeral=True)

@bot.tree.command(name="close", description="Close a support case")
@discord.app_commands.describe(case="Case ID to close")
async def close_case(interaction: discord.Interaction, case: int):
    """Close a support case"""
    if case not in bot.cases:
        await interaction.response.send_message("Case not found.", ephemeral=True)
        return
    
    case_data = bot.cases[case]
    case_data['status'] = 'closed'
    case_data['closed_at'] = datetime.utcnow()
    case_data['closed_by'] = interaction.user.id
    
    # Archive thread
    thread = bot.get_channel(case_data['thread_id'])
    if thread:
        await thread.edit(archived=True)
        await thread.send(f"Case closed by {interaction.user.mention}")
    
    # Notify user
    user = bot.get_user(case_data['user_id'])
    if user:
        try:
            embed = discord.Embed(
                title=f"Case #{case} Closed",
                description="Your support case has been resolved. If you need further assistance, feel free to send another message.",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            await user.send(embed=embed)
        except discord.Forbidden:
            pass
    
    await interaction.response.send_message(f"Case #{case} has been closed.", ephemeral=True)

# Voice Channel Management Commands
def in_voice_channel():
    """Decorator to check if user is in a voice channel"""
    def predicate(interaction: discord.Interaction) -> bool:
        return bool(interaction.user.voice and interaction.user.voice.channel)
    return discord.app_commands.check(predicate)

@bot.tree.command(name="forcemute", description="Mute all members in your current voice channel")
@in_voice_channel()
async def force_mute(interaction: discord.Interaction):
    """Mute all members in the current voice channel"""
    voice_channel = interaction.user.voice.channel
    
    if not voice_channel.permissions_for(interaction.guild.me).mute_members:
        await interaction.response.send_message("I don't have permission to mute members in this channel.", ephemeral=True)
        return
    
    muted_count = 0
    for member in voice_channel.members:
        if not member.voice.mute and member != interaction.guild.me:
            try:
                await member.edit(mute=True)
                muted_count += 1
            except discord.Forbidden:
                continue
    
    await interaction.response.send_message(f"Muted {muted_count} members in {voice_channel.name}")

@bot.tree.command(name="private", description="Make your current voice channel private")
@in_voice_channel()
async def make_private(interaction: discord.Interaction):
    """Lock the voice channel to current members only"""
    voice_channel = interaction.user.voice.channel
    
    if not voice_channel.permissions_for(interaction.guild.me).manage_channels:
        await interaction.response.send_message("I don't have permission to modify this channel.", ephemeral=True)
        return
    
    # Get current members
    current_members = [member for member in voice_channel.members]
    
    # Set permissions
    overwrites = voice_channel.overwrites
    overwrites[interaction.guild.default_role] = discord.PermissionOverwrite(connect=False)
    
    for member in current_members:
        overwrites[member] = discord.PermissionOverwrite(connect=True)
    
    await voice_channel.edit(overwrites=overwrites)
    await interaction.response.send_message(f"🔒 {voice_channel.name} is now private to current members.")

@bot.tree.command(name="public", description="Make your current voice channel public")
@in_voice_channel()
async def make_public(interaction: discord.Interaction):
    """Unlock the voice channel for everyone"""
    voice_channel = interaction.user.voice.channel
    
    if not voice_channel.permissions_for(interaction.guild.me).manage_channels:
        await interaction.response.send_message("I don't have permission to modify this channel.", ephemeral=True)
        return
    
    # Reset permissions to allow everyone
    overwrites = voice_channel.overwrites
    if interaction.guild.default_role in overwrites:
        del overwrites[interaction.guild.default_role]
    
    await voice_channel.edit(overwrites=overwrites)
    await interaction.response.send_message(f"🔓 {voice_channel.name} is now public.")

@bot.tree.command(name="max", description="Set maximum member limit for your voice channel")
@discord.app_commands.describe(number="Maximum number of members (0 for unlimited)")
@in_voice_channel()
async def set_max_members(interaction: discord.Interaction, number: int):
    """Set maximum member limit for voice channel"""
    if number < 0 or number > 99:
        await interaction.response.send_message("Member limit must be between 0 and 99.", ephemeral=True)
        return
    
    voice_channel = interaction.user.voice.channel
    
    if not voice_channel.permissions_for(interaction.guild.me).manage_channels:
        await interaction.response.send_message("I don't have permission to modify this channel.", ephemeral=True)
        return
    
    await voice_channel.edit(user_limit=number)
    
    if number == 0:
        await interaction.response.send_message(f"Removed member limit from {voice_channel.name}")
    else:
        await interaction.response.send_message(f"Set member limit to {number} for {voice_channel.name}")

@bot.tree.command(name="desc", description="Set description for your voice channel")
@discord.app_commands.describe(description="Channel description/topic")
@in_voice_channel()
async def set_description(interaction: discord.Interaction, description: str):
    """Set description for voice channel"""
    voice_channel = interaction.user.voice.channel
    
    if not voice_channel.permissions_for(interaction.guild.me).manage_channels:
        await interaction.response.send_message("I don't have permission to modify this channel.", ephemeral=True)
        return
    
    await voice_channel.edit(topic=description)
    await interaction.response.send_message(f"Updated description for {voice_channel.name}")

@bot.tree.command(name="invite", description="Send voice channel invite to a user")
@discord.app_commands.describe(user="User to invite")
@in_voice_channel()
async def invite_user(interaction: discord.Interaction, user: discord.Member):
    """Send DM invite to user for voice channel"""
    voice_channel = interaction.user.voice.channel
    
    if not voice_channel.permissions_for(interaction.guild.me).create_instant_invite:
        await interaction.response.send_message("I don't have permission to create invites.", ephemeral=True)
        return
    
    try:
        invite = await voice_channel.create_invite(max_uses=1, max_age=3600)  # 1 hour
        
        embed = discord.Embed(
            title="🎙️ Voice Channel Invitation",
            description=f"{interaction.user.display_name} has invited you to join a voice channel!",
            color=discord.Color.blue()
        )
        embed.add_field(name="Channel", value=voice_channel.name, inline=True)
        embed.add_field(name="Server", value=interaction.guild.name, inline=True)
        embed.add_field(name="Invite Link", value=invite.url, inline=False)
        embed.set_footer(text="This invite expires in 1 hour")
        
        await user.send(embed=embed)
        await interaction.response.send_message(f"Sent voice channel invite to {user.display_name}", ephemeral=True)
        
    except discord.Forbidden:
        await interaction.response.send_message(f"Could not send DM to {user.display_name}. They may have DMs disabled.", ephemeral=True)

# Study & Productivity Commands
@bot.tree.command(name="topic", description="Get a random conversation starter or discussion topic")
async def random_topic(interaction: discord.Interaction):
    """Get a random conversation topic"""
    topic = random.choice(bot.topics)
    
    embed = discord.Embed(
        title="💬 Discussion Topic",
        description=topic,
        color=discord.Color.purple()
    )
    embed.set_footer(text="Great conversations start with great questions!")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="studyquote", description="Get a motivational study quote")
async def study_quote(interaction: discord.Interaction):
    """Get a motivational study quote"""
    quote = random.choice(bot.study_quotes)
    
    embed = discord.Embed(
        title="📚 Study Motivation",
        description=f"*\"{quote}\"*",
        color=discord.Color.gold()
    )
    embed.set_footer(text="Keep pushing forward! 💪")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pomodoro", description="Start a pomodoro timer")
@discord.app_commands.describe(
    focus_time="Focus time in minutes (default: 25)",
    break_time="Break time in minutes (default: 5)"
)
async def pomodoro_timer(interaction: discord.Interaction, focus_time: int = 25, break_time: int = 5):
    """Start a pomodoro timer"""
    if focus_time < 1 or focus_time > 120:
        await interaction.response.send_message("Focus time must be between 1 and 120 minutes.", ephemeral=True)
        return
    
    if break_time < 1 or break_time > 60:
        await interaction.response.send_message("Break time must be between 1 and 60 minutes.", ephemeral=True)
        return
    
    user_id = interaction.user.id
    
    if user_id in bot.active_timers:
        await interaction.response.send_message("You already have an active timer! Use `/stoptimer` to stop it first.", ephemeral=True)
        return
    
    # Store timer data
    bot.active_timers[user_id] = {
        'focus_time': focus_time,
        'break_time': break_time,
        'start_time': datetime.utcnow(),
        'phase': 'focus'
    }
    
    embed = discord.Embed(
        title="🍅 Pomodoro Timer Started",
        description=f"Focus time: **{focus_time} minutes**\nBreak time: **{break_time} minutes**\n\nStay focused! I'll notify you when it's time for a break.",
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text="Good luck with your study session!")
    
    await interaction.response.send_message(embed=embed)
    
    # Schedule focus completion
    await asyncio.sleep(focus_time * 60)
    
    if user_id in bot.active_timers:
        # Award XP
        if user_id not in bot.user_xp:
            bot.user_xp[user_id] = 0
        bot.user_xp[user_id] += 10
        
        embed = discord.Embed(
            title="⏰ Focus Time Complete!",
            description=f"Great job! You focused for {focus_time} minutes.\n\n**+10 XP earned!**\nTotal XP: {bot.user_xp[user_id]}\n\nTake a {break_time} minute break!",
            color=discord.Color.green()
        )
        
        try:
            await interaction.followup.send(embed=embed)
        except:
            user = bot.get_user(user_id)
            if user:
                try:
                    await user.send(embed=embed)
                except:
                    pass
        
        # Update timer phase
        bot.active_timers[user_id]['phase'] = 'break'
        
        # Schedule break completion
        await asyncio.sleep(break_time * 60)
        
        if user_id in bot.active_timers:
            embed = discord.Embed(
                title="☕ Break Time Over!",
                description="Break time is over. Ready for another focus session?",
                color=discord.Color.blue()
            )
            
            try:
                await interaction.followup.send(embed=embed)
            except:
                user = bot.get_user(user_id)
                if user:
                    try:
                        await user.send(embed=embed)
                    except:
                        pass
            
            del bot.active_timers[user_id]

@bot.tree.command(name="stoptimer", description="Stop your active pomodoro timer")
async def stop_timer(interaction: discord.Interaction):
    """Stop active pomodoro timer"""
    user_id = interaction.user.id
    
    if user_id not in bot.active_timers:
        await interaction.response.send_message("You don't have an active timer.", ephemeral=True)
        return
    
    del bot.active_timers[user_id]
    await interaction.response.send_message("⏹️ Timer stopped.", ephemeral=True)

@bot.tree.command(name="rank", description="Check your XP ranking")
async def check_rank(interaction: discord.Interaction):
    """Check XP ranking"""
    user_id = interaction.user.id
    user_xp = bot.user_xp.get(user_id, 0)
    
    # Sort users by XP
    sorted_users = sorted(bot.user_xp.items(), key=lambda x: x[1], reverse=True)
    
    # Find user's rank
    user_rank = None
    for i, (uid, xp) in enumerate(sorted_users):
        if uid == user_id:
            user_rank = i + 1
            break
    
    if user_rank is None:
        user_rank = "Unranked"
    
    embed = discord.Embed(
        title="📊 Your Study Ranking",
        color=discord.Color.gold()
    )
    
    embed.add_field(name="Your XP", value=f"**{user_xp}** XP", inline=True)
    embed.add_field(name="Your Rank", value=f"**#{user_rank}**", inline=True)
    embed.add_field(name="Total Users", value=f"**{len(sorted_users)}**", inline=True)
    
    # Show top 5 users
    leaderboard = ""
    for i, (uid, xp) in enumerate(sorted_users[:5]):
        user = bot.get_user(uid)
        name = user.display_name if user else f"User {uid}"
        leaderboard += f"{i+1}. **{name}** - {xp} XP\n"
    
    if leaderboard:
        embed.add_field(name="🏆 Top 5 Leaderboard", value=leaderboard, inline=False)
    
    embed.set_footer(text="Keep studying to climb the ranks!")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="remindme", description="Set a personal reminder")
@discord.app_commands.describe(
    time="Time until reminder (e.g., '30m', '2h', '1d')",
    message="Reminder message"
)
async def remind_me(interaction: discord.Interaction, time: str, message: str):
    """Set a personal reminder"""
    try:
        # Parse time
        time = time.lower().strip()
        if time.endswith('m'):
            minutes = int(time[:-1])
            if minutes < 1 or minutes > 10080:  # 1 week in minutes
                raise ValueError("Minutes must be between 1 and 10080 (1 week)")
            delta = timedelta(minutes=minutes)
        elif time.endswith('h'):
            hours = int(time[:-1])
            if hours < 1 or hours > 168:  # 1 week in hours
                raise ValueError("Hours must be between 1 and 168 (1 week)")
            delta = timedelta(hours=hours)
        elif time.endswith('d'):
            days = int(time[:-1])
            if days < 1 or days > 7:
                raise ValueError("Days must be between 1 and 7")
            delta = timedelta(days=days)
        else:
            raise ValueError("Time format must end with 'm', 'h', or 'd'")
        
        reminder_time = datetime.utcnow() + delta
        
        # Store reminder
        user_id = interaction.user.id
        if user_id not in bot.reminders:
            bot.reminders[user_id] = []
        
        bot.reminders[user_id].append({
            'time': reminder_time,
            'message': message,
            'set_time': datetime.utcnow()
        })
        
        embed = discord.Embed(
            title="⏰ Reminder Set",
            description=f"I'll remind you in **{time}** with the message:\n\n*\"{message}\"*",
            color=discord.Color.green(),
            timestamp=reminder_time
        )
        embed.set_footer(text="You'll be reminded at")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except ValueError as e:
        await interaction.response.send_message(f"❌ Invalid time format: {e}\n\nExamples: `30m`, `2h`, `1d`", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error setting reminder: {e}", ephemeral=True)

# Error handling for voice channel commands
@force_mute.error
@make_private.error
@make_public.error
@set_max_members.error
@set_description.error
@invite_user.error
async def voice_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CheckFailure):
        await interaction.response.send_message("❌ You need to be in a voice channel to use this command.", ephemeral=True)

# Run the bot
if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("Invalid Discord token. Please check your DISCORD_TOKEN environment variable.")
    except Exception as e:
        logger.error(f"An error occurred while running the bot: {e}")
