# This bot makes use of the alpha rewrite version of the discord.py API, as well as various third-party libraries to help commands work.
# DeployMC is licensed under the GNU GPLv3 open-source license. To learn more about the GNU GPLv3, read the full licensing terms here: https://www.gnu.org/licenses/gpl-3.0.en.html
# 
# Last updated: October 6, 2019
#
# ------------ #
#     Setup    #
# ------------ #

# Importing necessary libraries
import discord
from discord.ext import commands
from requests import get
import asyncio
import docker
import json
import os
import re
import secrets
import socket
import string
import subprocess
import time
import random

# Creating objects
bot = commands.Bot(command_prefix='?')
client = docker.from_env()
ip = get('https://api.ipify.org').text
bot.remove_command('help')
CONFIG = json.loads(open("config.json").read())
alphabet = string.ascii_letters + string.digits
activity_out = bot.get_channel(615550634489282697)

# Setting some global emojis
e_yes = '✅'
e_no = '❌'
e_one = "1⃣"
e_two = "2⃣"
e_three = "3⃣"
e_four = "4⃣"
emoji_nums = ["1⃣", "2⃣", "3⃣", "4⃣", "5⃣", "6⃣", "7⃣", "8⃣", "9⃣", "🔟"]

# ----------- #
#  Functions  #
# ----------- #

# Log-in confirmation to console
@bot.event
async def on_ready():
	print('Logged in as: {}'.format(bot.user))
	print('User ID: {}'.format(bot.user.id))
	print('------')
	activity_out = bot.get_channel(615550634489282697)
	await activity_out.send("I'm here!")
	game = discord.Game("?help")
	await bot.change_presence(status=discord.Status.online, activity=game)

# Async communications function
async def async_comms(command, args):
	reader, writer = await asyncio.open_unix_connection("/tmp/docker.socket")
	writer.write(json.dumps({'command': command, 'args': args}).encode())
	data = await reader.read(1024)
	print (data)
	return json.loads(data.decode())

# Error handling
def error_handler (jsonData):
	if jsonData['result'] == 'container not found':
		return "You don't seem to have an instance created. Do that before running any server commands!"

# Randomly generate name
def name_generator():
	animals = open('/misc/animals.txt').read().splitlines()
	adjectives = open('/misc/adjectives.txt').read().splitlines()
	nouns = open('/misc/nouns.txt').read().splitlines()
	name = string.capwords(random.choice(adjectives)) + string.capwords(random.choice(nouns)) + string.capwords(random.choice(animals))
	return name
	#return ''.join(secrets.choice(alphabet) for i in range(12))

# Instance_picker
@bot.event
async def instance_picker(ctx, module, arg=None):
	container_name = ""
	jsonData = await async_comms('request', {'request': 'name', 'owner': str(ctx.message.author.id)})
	if jsonData['status'] == 'success':
		names_list = jsonData['result']
		inst_num = len(names_list)
		if (inst_num > 1):
			emoji_list = []
			for x in range(inst_num):
				list.append(emoji_list, emoji_nums[x])
			print (emoji_list)	
			inst_list = "\n".join("{} {}".format(first, second) for first, second in zip(emoji_list, names_list))
			embed = discord.Embed(title = "Which instance would you like to select?", description = re.sub("\ |\[|'|\]", "", inst_list), color=0xCC00FF)
			message = await ctx.send(embed=embed)
			for x in range(inst_num):
				await message.add_reaction(emoji_list[x])
			@bot.event
			async def on_reaction_add(reaction, user):
				if user.id == ctx.message.author.id:
					container_name = '{}'.format(*names_list[emoji_list.index(reaction.emoji)])
					if (module.__name__ == 'cmd_module'):
						await module(ctx, container_name, arg)
					else:
						await module(ctx, container_name)
		else:
			container_name = '{}'.format(*names_list[0])
			if (module.__name__ == 'cmd_module'):
				await module(ctx, container_name, arg)
			else:
				await module(ctx, container_name)

####### COMMAND MODULES FOR INSTANCE PICKER #######
# Start instance module
@bot.event
async def start_module(ctx, container_name):
	embed = discord.Embed(title = ":fox: :hourglass: Starting...", description = 
	"I'm downloading your instance files from our servers so it may take a while if you have a big world. Please bear with us!", color=0xffa500)
	in_progress = await ctx.send(embed=embed)
	jsonData = await async_comms('start', {'container': container_name, 'friendly_name': container_name})
	if jsonData['status'] == 'success':
		if jsonData['result'] == 'started':
			await in_progress.delete()
			embed = discord.Embed(title = ":fox: :arrow_forward: Instance started.", description = "Instance owned by " + str(ctx.message.author.mention) + " has started.\n" +
			"Note: If you can't join the server yet, give it another ~30 seconds for it to fully boot.", color=0x00AA00)
			await ctx.send(embed=embed)
			print(str(ctx.message.author.name) + " has started their instance.")
			activity_out = bot.get_channel(615550634489282697)
			await activity_out.send("<@" + str(ctx.message.author.id) + ">" + " has started their instance.")
		elif jsonData['result'] == 'already started':
			await in_progress.delete()
			embed = discord.Embed(title = ":fox: :x: Already running", description = "Your instance is already running.", color = 0x800000)
			await ctx.send(embed=embed)
			print(str(ctx.message.author.name) + " tried to start an already-running instance.")
			activity_out = bot.get_channel(615550634489282697)
			await activity_out.send("<@" + str(ctx.message.author.id) + ">" + " tried to start an already-running instance.")
		elif jsonData['result'] == 'insufficient funds':
			await in_progress.delete()
			embed = discord.Embed(title = ":fox: :x: Insufficient funds", description = "You don't seem to have enough money in your account. Make sure to load your balance before making an instance!", color = 0x800000)
			await ctx.send(embed=embed)
			print(str(ctx.message.author.name) + " tried to start their instance but had insufficient funds.")
			activity_out = bot.get_channel(615550634489282697)
			await activity_out.send("<@" + str(ctx.message.author.id) + ">" + " tried to start their instance but had insufficient funds.")
	else: 
		print("There was an error starting the instance.")
		embed = discord.Embed(title = ":fox: :x: Error!", description = "The instance could not be started. Are you sure you have an instance created?", color = 0x800000)
		await ctx.send(embed=embed)
		print("There was an error stopping the instance.")

# Stop instance module
@bot.event
async def stop_module(ctx, container_name):
	embed = discord.Embed(title = ":fox: :hourglass: Stopping...", description = 
	"I'm uploading your instance files to our servers so it may take a while if you have a big world. Please bear with us!", color=0xffa500)
	in_progress = await ctx.send(embed=embed)
	jsonData = await async_comms('stop', {'container': str(container_name), 'friendly_name': container_name})
	if jsonData['status'] == 'success':
		if jsonData['result'] == 'stopped':
			await in_progress.delete()
			embed = discord.Embed(title = ":fox: :stop_button: Instance stopped.", description = "Instance owned by " + str(ctx.message.author.mention) + " has been stopped.", color=0xB20000)
			await ctx.send(embed=embed)
			print(str(ctx.message.author.name) + " has stopped their instance.")
			activity_out = bot.get_channel(615550634489282697)
			await activity_out.send("<@" + str(ctx.message.author.id) + ">" + " has stopped their instance.")
		elif jsonData['result'] == 'already stopped':
			await in_progress.delete()
			embed = discord.Embed(title = ":fox: :x: Already stopped", description = "Your instance has already been stopped.", color = 0x800000)
			await ctx.send(embed=embed)
			print(str(ctx.message.author.name) + " tried to stop an already-stopped instance.")
			activity_out = bot.get_channel(615550634489282697)
			await activity_out.send("<@" + str(ctx.message.author.id) + ">" + " tried to stop an already-stopped instance.")
	else:
		embed = discord.Embed(title = ":fox: :x: Error!", description = "The instance could not be stopped. Are you sure you have an instance created?", color = 0x800000)
		await ctx.send(embed=embed)
		print("There was an error stopping the instance.")

# Status module
@bot.event
async def status_module(ctx, container_name):
	port_data = await async_comms('request', {'request': 'port', 'name': container_name})
	port = str(port_data['result'])
	jsonData = await async_comms('status', {'container': container_name})
	if jsonData['status'] == 'success':
		# For later // +str(jsonData['result']['server_type'])+" "
		# uptime = jsonData['result']['uptime']
		embed = discord.Embed(title = ":fox: :heart_decoration: Status check", description = "**"+str(ctx.message.author.name)+"'s " + str(jsonData['result']['version']) +
			" Server** \n"+ "Server address: 167.99.92.35:" + re.sub("\ |\[|\]", "", port) + "\nStatus: " + str(jsonData['result']['status']) + "\nPlayers online: " + str(jsonData['result']['players']['online']) + "/" + 
			str(jsonData['result']['players']['max']) + "\nDescription: " + str(jsonData['result']['description']['text']) + "\nRAM usage: " + 
			str(round((jsonData['result']['ram_usage'])/1000000)) + "MB", color=0xFFC0CB) #  + "\nUptime: " + str(uptime) + "s"
		await ctx.send(embed=embed)
		print(str(ctx.message.author.name) + " has status checked their instance.")
		activity_out = bot.get_channel(615550634489282697)
		await activity_out.send("<@" + str(ctx.message.author.id) + ">" + " has status checked their instance.")

	else: 
		embed = discord.Embed(title = ":fox: :x: Error!", description = "There was an error checking the status of the instance. \n\n" + 
		"Note: If you just started the instance it may still be booting up. Please give it 30 seconds or so before running a status check!", color=0x800000)
		await ctx.send(embed=embed)
		print("There was an error checking the status of the instance. Error output: " + jsonData['result'])
	print (jsonData)

# Delete instance module
@bot.event
async def delete_module(ctx, container_name):
	embed = discord.Embed(title = ":fox: :warning: Wait!", description = "Are you sure you want to delete your instance? Its data will be irrecoverable once you delete it.", color=0xFFBF00)
	message = await ctx.send(embed=embed)
	await message.add_reaction(e_yes)
	await message.add_reaction(e_no)
	@bot.event
	async def on_reaction_add(reaction, user):
		if user.id == ctx.message.author.id:
			if reaction.emoji == e_yes:
				print(container_name)
				jsonData = await async_comms('delete', {'container': container_name, 'name': container_name})
				if jsonData['status'] == 'success':
					await message.delete()
					embed = discord.Embed(title = ":fox: :wastebasket: Instance deleted.", description = "Instance owned by " + str(ctx.message.author.mention) + " has been deleted.", color=0xFF0000)
					await ctx.send(embed=embed)
					print(str(ctx.message.author.name) + " has deleted their instance.")
					activity_out = bot.get_channel(615550634489282697)
					await activity_out.send("<@" + str(ctx.message.author.id) + ">" + " has deleted their instance.")

				else: 
					embed = discord.Embed(title = ":fox: :x: Error!", description = "The instance could not be deleted and I'm not quite sure why. Join the Lyra Discord server and open a ticket if you need help: https://discord.gg/XJSwzsC", color = 0x800000)
					await ctx.send(embed=embed)
					print("There was an error deleting the instance.")
			elif reaction.emoji == e_no:
				await message.delete()
				embed = discord.Embed(title = ":fox: :x: Cancelled.", description = "", color=0xFF0000)
				await ctx.send(embed=embed)

# Minecraft command module
@bot.event
async def cmd_module(ctx, container_name, arg):
	jsonData = await async_comms('inject', {'container': container_name, 'injectcommand': arg})
	if jsonData['status'] == 'success':
		embed = discord.Embed(title = ":fox: :white_check_mark: Command run.", description = "", color=0x595959)
		await ctx.send(embed=embed)
		activity_out = bot.get_channel(615550634489282697)
		await activity_out.send("<@" + str(ctx.message.author.id) + ">" + " has run a Minecraft command.")
	else:
		embed = discord.Embed(title = ":fox: :x: Error!", description = "The command could not be run. Are you sure you have an instance running?", color = 0x800000)
		await ctx.send(embed=embed)
		print ("The instance could not be created.")

# ------------ #
#   Commands   #
# ------------ #

# Test ping command
@bot.command()
async def ping(ctx):
	await ctx.send("Pong!")
	await ctx.send(ctx.message.author.id)

# List containers command 
@bot.command()
async def containerlist(ctx):
	jsonData = await async_comms('list', {})
	await ctx.send(jsonData['result'])

# Help command
@bot.command()
async def help(ctx):
	#embed = discord.Embed(title = ":tools: Help", description = 
	#   "?new (Starts the setup process to create a new instance.)" +
	#"\n ?start (Starts your instance.)" 
	#"\n ?stop (Stops your instance.)+ " 
	#"\n ?delete (Stops and deletes your instance.)" +
	#"\n ?status (Gives current status of your instance.)" +
	#"\n ?cmd <command> (Runs the specified Minecraft command on your instance.)" +
	#"\n\n Need more help? Ask over at the official <name> Discord server: <url>"
	embed=discord.Embed(title=":fox: :tools: Lyra Help", color=0xff80ff)
	embed.add_field(name="?new", value="Creates a new instance.", inline=False)
	embed.add_field(name="?start", value="Starts your instance.", inline=False)
	embed.add_field(name="?stop", value="Stops your instance.", inline=False)
	embed.add_field(name="?status" , value="Retrieves information on instance.", inline=False)
	embed.add_field(name="?delete", value="Deletes your instance.", inline=False)
	embed.add_field(name="?cmd <command>", value="Injects command into game-server.", inline=False)
	embed.add_field(name="?bal", value="Checks account balance.", inline=False)
	embed.add_field(name="?load", value="Claims trial credit.", inline=False)
	embed.set_footer(text="Need more help? Ask over at the official Lyra Discord server: https://discord.gg/XJSwzsC")
	await ctx.send(embed=embed)

# Load balance (current form is intended purely for testing)
@bot.command()
async def load(ctx):
	jsonData = await async_comms('balance', {'action': 'load', 'name': str(ctx.message.author.id)})
	if jsonData['status'] == 'success':
		if jsonData['result'] == 'loaded':
			embed = discord.Embed(title = ":fox: :white_check_mark: Load successful!", description = "I've loaded your balance with 48 hours worth of server uptime for you to play with during the beta stage. Have fun with it!", color=0x1DCD49)
			await ctx.send(embed=embed)
			print(str(ctx.message.author.name) + " has loaded their balance with $10.")
			activity_out = bot.get_channel(615550634489282697)
			await activity_out.send("<@" + str(ctx.message.author.id) + ">" + " has loaded their balance with $10.")

		elif jsonData['result'] == 'duplicate':
			embed = discord.Embed(title = ":fox: :x: Load unsuccessful.", description = "You've already claimed your free credits. Don't be greedy!", color=0xD51717)
			await ctx.send(embed=embed)

# Check balance
@bot.command()
async def bal(ctx):
	jsonData = await async_comms('balance', {'action': 'check', 'name': str(ctx.message.author.id)})
	balance = '{:.2f}'.format(round(float(jsonData['result']), 2))
	if jsonData['status'] == 'success':
		embed = discord.Embed(title = ":fox: :dollar: Balance check", description = "You have **$" + str(balance) + "** in your account.", color=0x1DCD49)
		await ctx.send(embed=embed)
	
# Start container
@bot.command()
async def start(ctx):
	await instance_picker(ctx, start_module)
	
# Stop container
# @sends_container(command="stop") (this hasn't been implemented yet)
@bot.command()
async def stop(ctx):
	await instance_picker(ctx, stop_module)

# Force stop any container (admins only)
@bot.command()
async def adminstop(ctx, containername):
	if str(ctx.message.author.id) == "223453942003138562" or "474209567690063881":
		jsonData = await async_comms('stop', {'container': containername})
		if jsonData['status'] == 'success':
			embed = discord.Embed(title = ":fox: :stop_button: Instance stopped.", description = "Admin " + str(ctx.message.author.mention) + " has adminstopped an instance.", color=0xB20000)
			await ctx.send(embed=embed)
			print(str(ctx.message.author.name) + " has adminstopped an instance.")
		else:
			embed = discord.Embed(title = ":fox: :x: Error!", description = "The instance could not be stopped.", color = 0x800000)
			await ctx.send(embed=embed)

# Delete container
@bot.command()
async def delete(ctx):
	await instance_picker(ctx, delete_module)
	
# Healthcheck
@bot.command()
async def status(ctx):
	await instance_picker(ctx, status_module)

# Create new server
@bot.command()
async def new(ctx):
	freeport = findfreeport()
	server_type = 'none'

	# Game variant (Java, Bedrock, Cuberite, etc.)
	embed = discord.Embed(title = "Instance creator", description = "Which variant of Minecraft would you like your instance to run?" +
	"\n\n:one: Java  \n:two: Bedrock", color=0x198C19)
	message = await ctx.send(embed=embed)
	await message.add_reaction(e_one)
	await message.add_reaction(e_two)
	@bot.event
	async def on_reaction_add(reaction, user):
		if user.id == ctx.message.author.id:
			if reaction.emoji == e_one: 
				game = 'JAVA'
				# Variant of Java (Vanilla, Paper, Forge, etc.)
				embed = discord.Embed(title = "Instance creator", description = "Which Java variant would you like your instance to run?" +
				"\n\n:one: Paper (recommended)  \n:two: Vanilla \n\n Forge support coming soon!", color=0x198C19)
				message = await ctx.send(embed=embed)
				await message.add_reaction(e_one)
				await message.add_reaction(e_two)
				# await message.add_reaction(e_three)
				@bot.event
				async def on_reaction_add(reaction, user):
					if user.id == ctx.message.author.id:
						if reaction.emoji == e_one: server_type = 'PAPER'
						elif reaction.emoji == e_two: server_type = 'VANILLA'
						# elif reaction.emoji == e_three: server_type = 'FORGE'

						# Version of Java Minecraft
						embed = discord.Embed(title = "Instance creator", description = "Which version would you like your instance to run?" +
						"\n\n:one: 1.12.2 (recommended) \n:two: 1.13.2 \n:three: 1.14.4 \n\nMore coming soon!", color=0x198C19)
						message = await ctx.send(embed=embed)
						await message.add_reaction(e_one)
						await message.add_reaction(e_two)
						await message.add_reaction(e_three)
						
						@bot.event
						async def on_reaction_add(reaction, user):
							if user.id == ctx.message.author.id:
								if reaction.emoji == e_one: version = '1.12.2'
								elif reaction.emoji == e_two: version = '1.13.2'
								elif reaction.emoji == e_three: version = '1.14.4'
								picked_name = name_generator()
								#elif reaction.emoji == e_four:
									#embed = discord.Embed(title = "Please tell me what version you'd like to use.", description = "", color=0x198C19)
									#await ctx.send(embed=embed)
								jsonData = await async_comms('create', {'name': picked_name, 'owner': str(ctx.message.author.id), 'port': freeport, 'game': game, 'memory': '1G', 'server_type': server_type, 'version' : version})
								if jsonData['status'] == 'success' and jsonData['result'] == 'created':
									embed = discord.Embed(title = ":sparkles: Instance " + "**" + picked_name + "**" + " created!", description = "**"+version+"** Minecraft instance owned by" + str(ctx.message.author.mention) + " created at: " + "**" + ip + ":" + freeport + "**" + "\n\nPlease wait around 30 seconds for instance startup.", color=0x198C19)
									await ctx.send(embed=embed)
									activity_out = bot.get_channel(615550634489282697)
									await activity_out.send("<@" + str(ctx.message.author.id) + ">" + " created an instance.")
								elif jsonData['status'] == 'success' and jsonData['result'] == 'insufficient funds':
									embed = discord.Embed(title = ":fox: :x: Insufficient funds", description = "You don't seem to have enough money in your account. Make sure to load your balance before making an instance!", color = 0x800000)
									await ctx.send(embed=embed)
									activity_out = bot.get_channel(615550634489282697)
									await activity_out.send("<@" + str(ctx.message.author.id) + ">" + " tried to create an instance but had insufficient funds.")
								else: 
									embed = discord.Embed(title = ":fox: :x: Error!", description = "The instance could not be created and I'm not quite sure why. Join the Lyra Discord server and open a ticket if you need help: https://discord.gg/XJSwzsC", color = 0x800000)
									await ctx.send(embed=embed)
									print ("The instance could not be created.")

			elif reaction.emoji == e_two: 
				game = 'BEDROCK'
				picked_name = name_generator()
				jsonData = await async_comms('create', {'name': picked_name, 'owner': str(ctx.message.author.id), 'port': freeport, 'game': game, 'memory': '512M'})
				if jsonData['status'] == 'success':
					embed = discord.Embed(title = ":sparkles: Instance " + "**" + picked_name + "**" + " created!", description = "Minecraft Bedrock instance owned by" + str(ctx.message.author.mention) + " created at: " + "**" + ip + ":" + freeport + "**" + "\n\nPlease wait around 30 seconds for instance startup.", color=0x198C19)
					await ctx.send(embed=embed)
					print(str(ctx.message.author.name) + " has created an instance.")
				else: print ("The instance could not be created.")

# Enter any server command
@bot.command()
async def cmd(ctx, *, arg):
	await instance_picker(ctx, cmd_module, arg)

# v2 front-end
@bot.command()
async def v2(ctx):
	e_start = '▶'
	e_stop = '⏹'
	e_status = '💟'
	e_delete = '🗑'

	embed = discord.Embed(title = ":fox: :tools: Toolbox", description = "__What would you like to do?__\n:arrow_forward: Start server \n:stop_button: Stop server \n"+
	":heart_decoration:Check status of server \n:wastebasket:Delete server", color=0x595959)
	message = await ctx.send(embed=embed)
	await message.add_reaction(e_start)
	await message.add_reaction(e_stop)
	await message.add_reaction(e_status)
	await message.add_reaction(e_delete)

	@bot.event
	async def on_reaction_add(reaction, user):
		if user.id == ctx.message.author.id:
			if reaction.emoji == e_start:
				await ctx.invoke(start)
			elif reaction.emoji == e_stop:
				await ctx.invoke(stop)
			elif reaction.emoji == e_status:
				await ctx.invoke(status)
			elif reaction.emoji == e_delete:
				await ctx.invoke(delete)

# ------------- #
# Network Stuff #
# ------------- #

def findfreeport():
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.bind(('', 0))
    addr, port = tcp.getsockname()
    tcp.close()
    return str(port)
	
# Token for bot to run here
bot.run(CONFIG["token"], bot=True)
