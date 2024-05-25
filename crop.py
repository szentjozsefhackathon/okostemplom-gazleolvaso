import cv2
import torch

class CropOutNumbers:
    def __init__(self, path, sx, sy, ex, ey, split_size, start):
        #self.picture = cv2.imread(path)
        self.picture = path
        self.picture = self.picture[sx:ex, sy:ey] # Define the region to be cut out here
        self.splitted = [self.picture[:, i:i+split_size] for i in range(start, self.picture.shape[1], split_size)]

    def show_img(self):
        cv2.imshow('image', self.picture)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        for p in self.splitted:
            cv2.imshow('image', p)
            cv2.waitKey(0)
            cv2.destroyAllWindows()