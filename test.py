import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

import json

df = pd.read_csv('./stats.csv', index_col=[0])

hubJson = json.load(open('hubs.json', encoding="utf-8"))
hubList = [ value for value in hubJson.values() if value['fch-enabled'] != False ]

hubNames = list()

for hub in hubList:
    print('Hubs:', hub['shortname'])
    hubNames.append("/" + hub['shortname'])

pairList = [(f1, f2) for f1 in hubNames for f2 in hubNames if f1 != f2]

array = np.zeros((len(hubList), len(hubList)))

for pair in pairList:
    src = pair[0]
    dst = pair[1]
    #count the number of successful pings between src and dst
    new_df = df[(df.src == src) &
                (df.dst == dst) &
                (df.status == 0)]
    count = len(new_df.index)
    print("src:", src, "dst:", dst, "count:", count)
    #put the count into a matrix that will be used within a heatmap
    i = hubNames.index(src)
    j = hubNames.index(dst)
    array[i][j] = count


print(array)

heatmap = pd.DataFrame(array, index=hubNames, columns=hubNames)
sns.heatmap(heatmap, annot=True)
plt.show()
