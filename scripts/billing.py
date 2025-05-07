import docker
import mysql.connector

client = docker.from_env()
mysql_connection = mysql.connector.connect(user='runner', password='PASSWORD', database='deploymc')
cursor = mysql_connection.cursor()

def update_billing(container):
    insufficient_funds = 0
    # Moving uptime to billed_time in intervals of 60
    cursor.execute("SELECT uptime FROM instances WHERE container_id = %s", (str(container.id),))
    result = cursor.fetchall()
    uptime_list = [list(i) for i in result]
    uptime_str = str(uptime_list).strip('[](),')
    uptime = int(uptime_str)
    if uptime % 1 == 0:
        cursor.execute("UPDATE instances SET billed_time = %s WHERE container_id = %s", (str(uptime), str(container.id)))
        mysql_connection.commit()

    # Grabbing billed_time
    cursor.execute("SELECT billed_time FROM instances WHERE container_id = %s", (str(container.id),))
    result = cursor.fetchall()
    billed_time_list = [list(i) for i in result]
    billed_time_str = str(billed_time_list).strip('[](),')
    billed_time = int(billed_time_str)
    
    # Start the billing cycle
    if billed_time != 0 and billed_time % 1 == 0:
        # Get the owner of the instance
        cursor.execute("SELECT owner FROM instances WHERE container_id = %s", (str(container.id),))
        result = cursor.fetchall()
        owner_list = [list(i) for i in result]
        owner = str(owner_list).strip("[]()'',")

        # Get the instance type
        cursor.execute("SELECT type FROM instances WHERE container_id = %s", (str(container.id),))
        result = cursor.fetchall()
        inst_type_list = [list(i) for i in result]
        inst_type = str(inst_type_list).strip("[]()'',")
        print(inst_type)

        # Get pricing based on instance type
        cursor.execute("SELECT price FROM prices WHERE name = %s", (str(inst_type),))
        result = cursor.fetchall()
        price_list = [list(i) for i in result]
        price_str = str(price_list).strip('[](),')
        price = float(price_str)
        # Minutely billing cause cron hates this script when it's hourly
        price = price/60

        # Get balance of owner
        cursor.execute("SELECT balance FROM accounts WHERE discord_id = %s", (str(owner),))
        result = cursor.fetchall()
        balance_list = [list(i) for i in result]
        balance_str = str(balance_list).strip('[](),')
        balance = float(balance_str)
        
        # Check if owner can afford the instance
        if (price > balance):
            insufficient_funds = True
            cursor.execute("UPDATE instances SET status = 'insufficient funds' WHERE owner = %s", (str(owner),))
            mysql_connection.commit()

        # Deduct funds as long as owner does not have insufficient funds
        if (insufficient_funds == False):
            cursor.execute("UPDATE accounts SET balance = %s WHERE discord_id = %s", (str(balance-price), str(owner)))
            cursor.execute("UPDATE instances SET billed_time = %s WHERE container_id = %s", (str(billed_time), str(container.id)))
            mysql_connection.commit()

for container in client.containers.list():
    update_billing(container)
