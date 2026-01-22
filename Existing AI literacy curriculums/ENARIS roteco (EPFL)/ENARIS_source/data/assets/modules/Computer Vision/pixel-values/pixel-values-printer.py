import seaborn as sns
import matplotlib.pyplot as plt

#decomment for figure of pixe values
#image_greyscale = [[0, 50, 100, 150, 200, 255]]

image_matrix = [[0,  0,   0,   9,   27,  25,  7,   0,   0],
                [0,  8,   68,  191, 207, 187, 45,  2,   0],
                [6,  94,  215, 255, 254, 255, 184, 51,  0],
                [12, 201, 240, 218, 145, 239, 230, 149, 14],
                [30, 235, 245, 122, 11,  177, 240, 210, 50],
                [34, 251, 255, 72,  0,   125, 255, 234, 85],
                [40, 245, 255, 51,  0,   97,  255, 248, 119],
                [54, 243, 255, 59,  0,   105, 255, 244, 107],
                [37, 230, 255, 83,  0,   131, 255, 233, 82],
                [4,  200, 254, 151, 31,  192, 240, 206, 47],
                [3,  175, 245, 238, 187, 247, 230, 140, 11],
                [2,  175, 240, 238, 187, 247, 220, 140, 11],
                [0,  62,  188, 254, 255, 253, 168, 42,  0],
                [0,  2,   43,  163, 180, 154, 31,  1,   0],
                [0,  0,   0,   14,  22,  10,  0,   0,   0]]

#decomment for figure of pixe values
#plt.figure(figsize=(10,5))

plt.figure(figsize=(13,12))
plt.ticklabel_format(style='plain', axis='y',useOffset=False)
ax = sns.heatmap(
    #decomment for figure of pixe values
    #image_greyscale, 
    image_matrix,
    annot=True, 
    cmap="gist_gray", 
    fmt='g', 
    annot_kws={
        'fontsize': 19,
        'fontweight': 'bold',
        'fontfamily': 'serif'})
plt.show()
