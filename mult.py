def mult(n):
    for i in range(1,13):
        print(i," x ", n," = ", i*n)

while True:
    var = int(input('enter a number : \t'))
    if var > 0 :
        break
mult(var)