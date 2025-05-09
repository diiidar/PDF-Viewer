import cv2 as cv

img = cv.imread(f'data/processed_pages/page_6.png')

img_neg = 1 - img

cv.imshow('w', img_neg)

cv.waitKey(0)