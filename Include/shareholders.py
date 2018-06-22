import requests
from bs4 import BeautifulSoup


def codong(cp):

    page = requests.get('https://www.stockbiz.vn/Stocks/VJC/MajorHolders.aspx')
    soup = BeautifulSoup(page.content, 'html.parser')


    table = soup.findAll('table')

    print(table)
    table = table[2]
    rows = table.findAll('tr')



codong('VJC')