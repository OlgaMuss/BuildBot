import cv2
import matplotlib.pyplot as plt

# Import Image as Greyscale
img = cv2.imread("../original_robot.png", 0)
img_gr = cv2.GaussianBlur(img, (3,3), 0)

# Figure Creation
fig = plt.figure(figsize=(10, 7))

#Detect X Edges
x_sobel = cv2.Sobel(img_gr, ddepth=cv2.CV_8U, dx=1, dy=0, ksize=5)
x_edges = cv2.Canny(image=x_sobel, threshold1=75, threshold2=225)

#Detect Y Edges
y_sobel = cv2.Sobel(img_gr, ddepth=cv2.CV_8U, dx=0, dy=1, ksize=5)
y_edges = cv2.Canny(image=y_sobel, threshold1=75, threshold2=225)

#Detect X+Y Edges
xy_edges = cv2.Canny(image=img_gr, threshold1=75, threshold2=225)


image_array = [img_gr, x_edges, y_edges, xy_edges]
image_titles = ['Bild in SW', 'Horizontale Kanten', 'Vertikale Kanten', 'Alle Kanten']
rows = 2
cols = 2

for i in range(4):
	fig.add_subplot(rows, cols, i+1)
	plt.imshow(image_array[i], cmap='gray')
	plt.title(image_titles[i])
	plt.xticks([])
	plt.yticks([])
plt.show()
