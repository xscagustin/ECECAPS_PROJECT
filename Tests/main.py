import pymysql

user_input= input("Input your username: ")
pass_input= input("Input your password: ")


# Connect to server
try:
    cnx = pymysql.connect(
        host="127.0.0.1",
        port=3306,
        user=user_input,
        password=pass_input)
    # Get a cursor
    cur = cnx.cursor()

    # Execute a query
    cur.execute("SELECT CURDATE()")

    # Fetch one result
    row = cur.fetchone()
    print("Current date is: {0}".format(row[0]))

    # Close connection
    cnx.close()
except:
    print("wrong login")

