import discord
from discord.ext import commands, tasks
import google.generativeai as genai
import aiohttp
import re
import config
from datetime import datetime, timedelta

GEMINI_API_KEY = config.GEMINI_API_KEY
DISCORD_BOT_TOKEN = config.DISCORD_BOT_TOKEN
AI_CHANNEL = config.CHANNEL_ID

message_history = {}
last_message_time = {}

genai.configure(api_key=GEMINI_API_KEY)
text_generation_config = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 512,
}
image_generation_config = {
    "temperature": 0.4,
    "top_p": 1,
    "top_k": 32,
    "max_output_tokens": 512,
}
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]
text_model = genai.GenerativeModel(model_name="gemini-2.0-flash", generation_config=text_generation_config, safety_settings=safety_settings)
image_model = genai.GenerativeModel(model_name="gemini-pro-vision", generation_config=image_generation_config, safety_settings=safety_settings)

bot_knowledge = [
    {'role':'user','parts': ["who are you"]},
    {'role':'model','parts': ["You are Synapse, Support Assistant AI ChatBot of Kito. Your purpose is to support people with their issues and doubts!"]},
    {'role':'user','parts': ["about Kito"]},
    {'role':'model','parts': ["Kito AKA Krtish Vaidhyan is an AI / ML Developer studying in class 12th and preparing for JEE entrance exam."]},
]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None, activity=discord.Game('Discord'))

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return
    last_message_time[message.channel.id] = datetime.utcnow()
    
    if isinstance(message.channel, discord.TextChannel) and message.channel.id == AI_CHANNEL:
        async with message.channel.typing():
            if message.attachments:
                print("New Image Message FROM:" + str(message.author.id) + ": " + message.content)
                for attachment in message.attachments:
                    if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                        await message.add_reaction('👀')

                        async with aiohttp.ClientSession() as session:
                            async with session.get(attachment.url) as resp:
                                if resp.status != 200:
                                    await message.channel.send('Unable to download the image.')
                                    return
                                image_data = await resp.read()
                                response_text = await generate_response_with_image_and_text(image_data, message.content)
                                await split_and_send_messages(message, response_text, 1700)
                                return
            else:
                print("New Message FROM:" + str(message.author.id) + ": " + message.content)
                response_text = await generate_response_with_text(message.channel.id, message.content)
                await split_and_send_messages(message, response_text, 1700)
                return
            
async def generate_response_with_text(channel_id, message_text):
    cleaned_text = clean_discord_message(message_text)

    if channel_id not in message_history:
        message_history[channel_id] = text_model.start_chat(history=bot_knowledge)

    response = message_history[channel_id].send_message(cleaned_text)
    return response.text

async def generate_response_with_image_and_text(image_data, text):
    image_parts = [{"mime_type": "image/jpeg", "data": image_data}]
    prompt_parts = [image_parts[0], f"\n{text if text else 'What is this a picture of?'}"]
    response = image_model.generate_content(prompt_parts)
    
    if response._error:
        return "❌" + str(response._error)
    
    return response.text

@bot.command(name='forget', description='Forget message history')
async def forget(ctx):
    try:
        message_history.pop(ctx.channel.id)
    except Exception:
        pass
    await ctx.send("Message history for this channel has been erased.")

async def split_and_send_messages(message_system: discord.Message, text, max_length):
    messages = [text[i:i+max_length] for i in range(0, len(text), max_length)]
    
    for msg in messages:
        message_system = await message_system.reply(msg)    

def clean_discord_message(input_string):
    bracket_pattern = re.compile(r'<[^>]+>')
    cleaned_content = bracket_pattern.sub('', input_string)
    return cleaned_content  

@tasks.loop(minutes=5)
async def check_and_forget():
    current_time = datetime.utcnow()
    for channel_id, last_time in list(last_message_time.items()):
        if (current_time - last_time) > timedelta(minutes=5):
            message_history.pop(channel_id, None)
            last_message_time.pop(channel_id, None)

@bot.event
async def on_ready():
    print(f'ThunderAI Logged in as {bot.user}')
    print("Bot is Created by Kito")
    print(f'Bot is ready to use')
    check_and_forget.start()

@bot.event
async def on_shutdown():
    check_and_forget.stop()
    
bot.run(DISCORD_BOT_TOKEN)