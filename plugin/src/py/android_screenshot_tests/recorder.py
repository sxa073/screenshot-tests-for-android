#!/usr/bin/env python
#
# Copyright (c) 2014-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.
#

import xml.etree.ElementTree as ET
import os
import sys

from os.path import join
from PIL import Image, ImageChops

from . import common
import shutil
import tempfile

from junit_xml import TestSuite, TestCase

class VerifyError(Exception):
    pass

class Recorder:
    def __init__(self, input, output, report_dir=None):
        self._input = input
        self._output = output
        self._expectedoutput = output
        self._report_dir = report_dir

    def _get_image_size(self, file_name):
        with Image.open(file_name) as im:
            return im.size

    def _copy(self, name, w, h):
        tilewidth, tileheight = self._get_image_size(
            join(self._input,
                 common.get_image_file_name(name, 0, 0)))

        canvaswidth = 0

        for i  in range(w):
            input_file = common.get_image_file_name(name, i, 0)
            canvaswidth += self._get_image_size(join(self._input, input_file))[0]


        canvasheight = 0

        for j in range(h):
            input_file = common.get_image_file_name(name, 0, j)
            canvasheight += self._get_image_size(join(self._input, input_file))[1]

        im = Image.new("RGBA", (canvaswidth, canvasheight))

        for i in range(w):
            for j in range(h):
                input_file = common.get_image_file_name(name, i, j)
                with Image.open(join(self._input, input_file)) as input_image:
                    im.paste(input_image, (i * tilewidth, j * tileheight))
                    input_image.close()

        im.save(join(self._output, name + ".png"))
        im.close()

    def _get_metadata_root(self):
        return ET.parse(join(self._input, "metadata.xml")).getroot()

    def _record(self):
        root = self._get_metadata_root()
        for screenshot in root.iter("screenshot"):
            self._copy(screenshot.find('name').text,
                       int(screenshot.find('tile_width').text),
                       int(screenshot.find('tile_height').text))

    def _clean(self):
        if os.path.exists(self._output):
            shutil.rmtree(self._output)
        os.mkdir(self._output)

    def _is_image_same(self, file1, file2):
        with Image.open(file1) as im1, Image.open(file2) as im2:
            diff_image = ImageChops.difference(im1, im2)
            try:
                return diff_image.getbbox() is None
            finally:
                diff_image.close()

    def _create_test_case(self, screenshot):
        test_class = screenshot.find('test_class').text
        test_name = screenshot.find('test_name').text
        return TestCase(test_name, test_class, elapsed_sec=1)

    def record(self):
        self._clean()
        self._record()

    def verify(self):
        self._output = tempfile.mkdtemp()
        self._record()

        errors = []
        test_cases = []
        root = self._get_metadata_root()
        for screenshot in root.iter("screenshot"):
            test_case = self._create_test_case(screenshot)

            name = screenshot.find('name').text + ".png"
            actual = join(self._output, name)
            expected = join(self._expectedoutput, name)

            if not self._is_image_same(expected, actual):
                errors.append("Image %s is not same as %s" % (actual, expected))
                test_case.add_failure_info(message="Image does not match")
                test_cases.append(test_case)
            
        shutil.rmtree(self._output)

        if self._report_dir is not None:
            print("Saving test result")
            test_suite = TestSuite("Screenshot Tests", test_cases)
            with open(os.path.join(self._report_dir, 'screenshot.xml'), 'w') as file:
                TestSuite.to_file(file, [test_suite])            
        
        if len(errors) > 0:
            raise VerifyError("\n".join(errors))
            

