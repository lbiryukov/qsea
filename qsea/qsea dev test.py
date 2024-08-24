import qsea
import logging
import datetime as dt

qsea.config.logQueryMaxLength = 300

logging.basicConfig(level=logging.DEBUG\
                    , format='%(asctime)s \t LineNo: %(lineno)s \t %(funcName)20s() \t %(levelname)s: %(message)s')

header_user = {'Authorization': 'Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJCaXJ5dWtvdi5MTiIsInVzZXJEaXJlY3RvcnkiOiJFS1NNTy1PRkZJQ0UifQ.G40lzAwpzJEa1YKSua649j4q27DZuKGFa7honMbiO2GJaOJzHDx5eyx69EfIZSxNbhvwPsuA3yB49rphPPjfYwavyqBKbpPaosvEwV0ySgDE5X8HVb9usJju3LTSvAcgocTM3oGEVWiGHgBYoGC9rKajzYQ1zilo6J7q7z9RoV8WxSRoH5HZHERIXSW9yGcSxtzt4txSb9Ep981lfcTR3QIXZZqVvKRr22m7H1PMIUhPCQ8c2Pelcc6Q6BDKMAuEaLvtikhP_gS2GUK67RY5GQZW8qOXaytx4bD9oQlUkqcDT1uM5eaEvIGOCDC7rW6xIb8bDl9JPCr3ACuYSBXvLoK9CeCphvm5ORbqXExuu6Oa2D_-m3mtLK-4J6btM93hxhxgvKVgHoeXw8YuGPmVBircH5n-0QiEJV246NZIuXqOHlO2xis2UJCUiqhBHOR_AYz_vLRACgOcmv-0G7tYL0ZElE6XHQwI-XDwYH7ga5KwSxwELg2ilj_6lvCC8nz2n7qRXjaGsZdB6BQ1Kvt3U54ckxPRg75Ot7bR4Ea4ZDchalxO2AdNP6GSDYRtC2EeP9FBlciAOHCys-0z2OWclI12ovjsTY_RU14wkYZjf8BmPuMzTtZwW475yNEMOtlC8CfnqG8gKTp32OFneWnwA_vx4KvTKCMRy2ygRMee1fg'}
qlik_url = "wss://co-qlik.eksmo-office.ru/edge/app/a16efac2-bd53-4b45-84f9-c6c535786816"

prefix = dt.datetime.strftime(dt.datetime.now(), '%Y%m%d%H%M%S')
logging.info('Prefix:, %s', prefix)
qsea.test()
print(qsea.__file__)


ws = qsea.OpenConnection(qlik_url, header_user)
# app = qsea.App(ws, 'Qlik Engine Test')
app = qsea.App(ws, 'Мерчендайзинг(2)')
app.reloadData()

# app.dimensions.load()

# df = qsea.GetDimPandas(ws, app.handle)
# print(df.columns)

# print(app.dimensions.df.columns)

# app.dimensions.add('NewDim' + prefix, definition = 'NewDimDef' + prefix, description = 'desc' + prefix, label = 'lbl' + prefix, \
#                  labelExpression = 'lblEx' + prefix)

app.save()
ws.close()
