import qsea
import logging
import datetime as dt
import pandas as pd

qsea.config.logQueryMaxLength = 300
logging.basicConfig(level=logging.INFO\
                    , format='%(asctime)s \t LineNo: %(lineno)s \t %(funcName)20s() \t %(levelname)s: %(message)s')

# logging.basicConfig(
#         level=logging.DEBUG,
#         filename='qsea_test.log',
#         filemode="w",
#         format='%(asctime)s \t LineNo: %(lineno)s \t %(funcName)20s() \t %(levelname)s: %(message)s')

header_user = {'Authorization': 'Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJCaXJ5dWtvdi5MTiIsInVzZXJEaXJlY3RvcnkiOiJFS1NNTy1PRkZJQ0UifQ.G40lzAwpzJEa1YKSua649j4q27DZuKGFa7honMbiO2GJaOJzHDx5eyx69EfIZSxNbhvwPsuA3yB49rphPPjfYwavyqBKbpPaosvEwV0ySgDE5X8HVb9usJju3LTSvAcgocTM3oGEVWiGHgBYoGC9rKajzYQ1zilo6J7q7z9RoV8WxSRoH5HZHERIXSW9yGcSxtzt4txSb9Ep981lfcTR3QIXZZqVvKRr22m7H1PMIUhPCQ8c2Pelcc6Q6BDKMAuEaLvtikhP_gS2GUK67RY5GQZW8qOXaytx4bD9oQlUkqcDT1uM5eaEvIGOCDC7rW6xIb8bDl9JPCr3ACuYSBXvLoK9CeCphvm5ORbqXExuu6Oa2D_-m3mtLK-4J6btM93hxhxgvKVgHoeXw8YuGPmVBircH5n-0QiEJV246NZIuXqOHlO2xis2UJCUiqhBHOR_AYz_vLRACgOcmv-0G7tYL0ZElE6XHQwI-XDwYH7ga5KwSxwELg2ilj_6lvCC8nz2n7qRXjaGsZdB6BQ1Kvt3U54ckxPRg75Ot7bR4Ea4ZDchalxO2AdNP6GSDYRtC2EeP9FBlciAOHCys-0z2OWclI12ovjsTY_RU14wkYZjf8BmPuMzTtZwW475yNEMOtlC8CfnqG8gKTp32OFneWnwA_vx4KvTKCMRy2ygRMee1fg'}
qlik_url = "wss://co-qlik.eksmo-office.ru/edge/app/"

prefix = dt.datetime.strftime(dt.datetime.now(), '%Y%m%d%H%M%S')
logging.info('Prefix:, %s', prefix)
qsea.test()
logging.info('File source: %s', qsea.__file__)


ws = qsea.OpenConnection(qlik_url, header_user)

qsea.GetAppID(ws, 'Qlik Engine Test')

len(qsea.GetAppList(ws))

app = qsea.App(ws, 'Qlik Engine Test')

app.load()
logging.info('var: %s', len(app.variables.df))
logging.info('ms: %s', len(app.measures.df))
logging.info('dim: %s', len(app.dimensions.df))
logging.info('fld: %s', len(app.fields.df))
logging.info('sh: %s', len(app.sheets.df))


logging.info('len(app.variables.df): %s', len(app.variables.df))

logging.info('создаём новую переменную')
app.variables.add('NewVar' + prefix, 'NewVarDef1')
logging.info('len(app.variables.df): %s', len(app.variables.df))


logging.info('меняем определение переменной, успешно')
var = app.variables['NewVar' + prefix]
var.name, var.definition
var.update(definition = 'NewVarDef2')

logging.info('создаём ещё одну переменную для удаления')
app.variables.add('NewVarDel' + prefix, 'NewVarDef1')
logging.info('len(app.variables.df): %s', len(app.variables.df))

logging.info('успешное удаление переменной')
app.variables['NewVarDel' + prefix].delete()
logging.info('len(app.variables.df): %s', len(app.variables.df))

logging.info('Успешное переименование переменной')
app.variables.add('NewVarRen' + prefix, 'NewVarDef1')
app.variables['NewVarRen' + prefix].rename('NewVarRenRen' + prefix)

app.variables.df.to_excel('test vars.xlsx')


logging.info('создаём новую меру')
app.measures.add('NewMs' + prefix, definition = 'NewMsDef' + prefix, description = 'desc' + prefix, label = 'lbl' + prefix, \
                 labelExpression = 'lblEx' + prefix)

logging.info('создаём ещё одну меру для удаления')
app.measures.add('NewDelMs' + prefix, definition = 'NewVarDef1')

logging.info('успешное удаление меры')
app.measures['NewDelMs' + prefix].delete()

logging.info('изменение меры')
app.measures.add('NewMsUpd' + prefix, definition = 'NewMsDef' + prefix, description = 'desc' + prefix, label = 'lbl' + prefix, \
                labelExpression = 'lblEx' + prefix)

app.measures['NewMsUpd' + prefix].update(definition = 'UpdatedDef' + prefix, label = 'UpdatedLabel' + prefix, \
                                         labelExpression = 'UpdatedLblEx' + prefix, \
                                         formatType = '', formatNDec = -1, formatUseThou = -1, formatDec = '', formatThou = '')

logging.info('переименование меры')
app.measures.add('NewMsRename' + prefix, definition = 'NewMsDef' + prefix, description = 'desc' + prefix, label = 'lbl' + prefix, \
                labelExpression = 'lblEx' + prefix)
app.measures['NewMsRename' + prefix].rename('NewMsRenamed' + prefix)

app.measures.df.to_excel('test ms.xlsx')



logging.info('создаём новое измерение')
app.dimensions.add('NewDim' + prefix, definition = 'NewDimDef' + prefix, description = 'desc' + prefix, label = 'lbl' + prefix, \
                 labelExpression = 'lblEx' + prefix)

logging.info('создаём ещё одно измерение для удаления')
app.dimensions.add('NewDelDim' + prefix, definition = 'NewDimDef' + prefix, description = 'desc' + prefix, label = 'lbl' + prefix)
logging.info('успешное удаление измерения')
app.dimensions['NewDelDim' + prefix].delete()

logging.info('изменение измерения')
app.dimensions.add('NewDimUpd' + prefix, definition = 'NewDimDef' + prefix, description = 'desc' + prefix, label = 'lbl' + prefix)
app.dimensions['NewDimUpd' + prefix].update(definition = 'UpdatedDef' + prefix, label = 'UpdatedLabel' + prefix)

logging.info('переименование измерения')
app.dimensions.add('NewDimRename' + prefix, definition = 'NewDimDef' + prefix, description = 'desc' + prefix, label = 'lbl' + prefix)
app.dimensions['NewDimRename' + prefix].rename('NewDimRenamed' + prefix)

app.dimensions.df.to_excel('test dim.xlsx')

logging.info('сохранение приложения')
app.save()

ws.close()