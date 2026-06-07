#!/data/data/com.termux/files/usr/bin/python

import imagehash
from PIL import Image


def find_similar_images(userpaths, hashfunc=imagehash.average_hash):

    def is_image(filename):
        f = filename.lower()
        return (
            f.endswith(".png")
            or f.endswith(".jpg")
            or f.endswith(".jpeg")
            or f.endswith(".bmp")
            or f.endswith(".gif")
            or (".jpg" in f)
            or f.endswith(".svg")
        )

    image_filenames = []
    for userpath in userpaths:
        image_filenames += [os.path.join(userpath, path) for path in os.listdir(userpath) if is_image(path)]
    images = {}
    for img in sorted(image_filenames):
        try:
            hash = hashfunc(Image.open(img))
        except Exception as e:
            print("Problem:", e, "with", img)
            continue
        if hash in images:
            print(img, "  already exists as", " ".join(images[hash]))
            if "dupPictures" in img:
                print("rm -v", img)
        images[hash] = images.get(hash, []) + [img]


if __name__ == "__main__":
    import os
    import sys

    def usage():
        sys.stderr.write(
            "SYNOPSIS: %s [ahash|phash|dhash|...] [<directory>]\nIdentifies similar images in the directory.\nMethod:\n  ahash:          Average hash\n  phash:          Perceptual hash\n  dhash:          Difference hash\n  whash-haar:     Haar wavelet hash\n  whash-db4:      Daubechies wavelet hash\n  colorhash:      HSV color hash\n  crop-resistant: Crop-resistant hash\n(C) Johannes Buchner, 2013-2017\n"
            % sys.argv[0]
        )
        sys.exit(1)

    hashmethod = sys.argv[1] if len(sys.argv) > 1 else usage()
    if hashmethod == "ahash":
        hashfunc = imagehash.average_hash
    elif hashmethod == "phash":
        hashfunc = imagehash.phash
    elif hashmethod == "dhash":
        hashfunc = imagehash.dhash
    elif hashmethod == "whash-haar":
        hashfunc = imagehash.whash
    elif hashmethod == "whash-db4":

        def hashfunc(img):
            return imagehash.whash(img, mode="db4")
    elif hashmethod == "colorhash":
        hashfunc = imagehash.colorhash
    elif hashmethod == "crop-resistant":
        hashfunc = imagehash.crop_resistant_hash
    else:
        usage()
    userpaths = sys.argv[2:] if len(sys.argv) > 2 else "."
    find_similar_images(userpaths=userpaths, hashfunc=hashfunc)
