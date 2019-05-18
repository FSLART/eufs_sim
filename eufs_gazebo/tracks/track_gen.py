#!/usr/bin/env python

"""track_gen.py

Script which generates CSV files from SDF Gazebo track models
CSV files consist of type of cones and their x and y positions
these CSV files are later intended to be used as input to a
ground truth cone publisher in simulation
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, tostring
from scipy import interpolate
from scipy.spatial import cKDTree
from xml.dom import minidom
import argparse
import os


class Track:
    def __init__(self):
        self.midpoints = None
        self.mid_track = None
        self.blue_cones = None
        self.blue_track = None
        self.yellow_cones = None
        self.yellow_track = None
        self.big_orange_cones = None
        self.orange_cones = None

    def load_csv(self, file_path):
        """Loads CSV file of cone location data and store it in the class.
        CSV file must have a 1 line header and then each row should have
        the format tag, x, y where tag is either "big", "blue", "orange" or "big_orange"

        Args:
            file_path (str): the path to the CSV file to load

        Returns:
            Nothing
        """

        if file_path.find(".csv") == -1:
            print("Please give me a .csv file. Exitting")
            return

        data = pd.read_csv(file_path, names=["tag", "x", "y"], skiprows=1)
        self.blue_cones = np.array(data[data.tag == "blue"][["x", "y"]])
        self.yellow_cones = np.array(data[data.tag == "yellow"][["x", "y"]])
        self.big_orange_cones = np.array(data[data.tag == "big_orange"][["x", "y"]])
        self.orange_cones = np.array(data[data.tag == "orange"][["x", "y"]])

    def load_sdf(self, file_path):
        """Loads a Gazebo model .SDF file and identify cones in it
        based on their mesh tag. Store as elements of the class.

        Args:
            file_path (str): the path to the SDF file to load

        Returns:
            Nothing
        """

        if file_path.find(".sdf") == -1:
            print("Please give me a .sdf file. Exitting")
            return

        root = ET.parse(file_path).getroot()
        blue = []
        yellow = []
        orange = []
        big_orange = []

        # iterate over all links of the model
        if len(root[0].findall("link")) != 0:
            for child in root[0].iter("link"):
                pose = child.find("pose").text.split(" ")[0:2]
                mesh_str = child.find("visual")[0][0][0].text.split("/")[-1]

                # indentify cones by the name of their mesh
                if "blue" in mesh_str:
                    blue.append(pose)
                elif "yellow" in mesh_str:
                    yellow.append(pose)
                elif "big" in mesh_str:
                    big_orange.append(pose)

        elif len(root[0].findall("include")) != 0:
            for child in root[0].iter("include"):
                pose = child.find("pose").text.split(" ")[0:2]
                mesh_str = child.find("uri").text.split("/")[-1]

                # indentify cones by the name of their mesh
                if "blue" in mesh_str:
                    blue.append(pose)
                elif "yellow" in mesh_str:
                    yellow.append(pose)
                elif "big" in mesh_str:
                    big_orange.append(pose)
                elif "orange" in mesh_str:
                    orange.append(pose)

        # convert all lists to numpy as arrays for efficiency
        self.blue_cones = np.array(blue, dtype="float64")
        self.yellow_cones = np.array(yellow, dtype="float64")
        if len(big_orange) != 0:
            self.big_orange_cones = np.array(big_orange, dtype="float64")
        if len(orange) != 0:
            self.orange_cones = np.array(orange, dtype="float64")

    def generate_tracks(self):
        """Generates blue, yellow and centerline tracks for the course
        and saves them within the class

        Args:
            None

        Returns:
            None
        """

        # Deal with blue cones
        if self.blue_cones.size is not None:
            self.blue_cones = self.order_points(self.blue_cones)
            self.blue_track = self.smoothLine(self.blue_cones)
        else:
            print("Warning: no blue/blue cones")

        # Deal with yellow cones
        if self.yellow_cones.size is not None:
            self.yellow_cones = self.order_points(self.yellow_cones)
            self.yellow_track = self.smoothLine(self.yellow_cones)
        else:
            print("Warning: no yellow/yellow cones")

        # Deal with midline
        if self.midpoints.size is not None:
            self.midpoints = self.order_points(self.midpoints)
            self.midline = self.smoothLine(self.midpoints)
        else:
            print("Warning: no midpoints")

    def generate_midpoints(self, _plot=False):
        """Generates track midpoints based on blue and yellow cones

        Args:
            file_path (str): the path to the SDF file to load

        Returns:
            Nothing
        """
        assert self.blue_cones is not None or len(self.yellow_cones) != 0
        assert self.yellow_cones is not None or len(self.yellow_cones) != 0

        midpoints = []

        for each in self.blue_cones:
            i, d = self.find_closest(each, self.yellow_cones)
            midpoints.append([(i[0] + each[0]) / 2, (i[1] + each[1]) / 2])

        if _plot:
            for each in self.blue_cones:
                i, d = self.find_closest(each, self.yellow_cones)
                self.plot_line(i, each)
                plt.plot((i[0] + each[0]) / 2, (i[1] + each[1]) / 2, 'bo')

            plt.show()

        self.midpoints = np.array(midpoints)

        return midpoints

    def plot_track(self):
        """Plot track in 2D with colours

        Args:
            None

        Returns:
            Nothing
        """
        fig, ax = plt.subplots()
        ax.set_xlim((-50, 50))
        ax.set_ylim((-50, 50))

        # Deal with blue cones
        if self.blue_cones.size is not None:
            plt.scatter(self.blue_cones[:, 0], self.blue_cones[:, 1], c="b", alpha="0.5")

            if self.blue_track is not None:
                plt.plot(self.blue_track[:, 0], self.blue_track[:, 1], "b-")
        else:
            print("Warning: no blue/blue cones")

        # Deal with yellow cones
        if self.yellow_cones.size is not None:
            plt.scatter(self.yellow_cones[:, 0], self.yellow_cones[:, 1], c="y", alpha="0.5")

            if self.yellow_track is not None:
                plt.plot(self.yellow_track[:, 0], self.yellow_track[:, 1], "y-")
        else:
            print("Warning: no yellow/yellow cones")

        if self.big_orange_cones is not None:
            plt.scatter(self.big_orange_cones[:, 0], self.big_orange_cones[:, 1], c="r", alpha="0.5")
        else:
            print("Warning: no big cones")

        if self.midpoints is not None:
            plt.scatter(self.midpoints[:, 0], self.midpoints[:, 1], c="g")

            if self.midline is not None:
                plt.plot(self.midline[:, 0], self.midline[:, 1], "g-")

        plt.axis('equal')
        plt.grid()
        plt.savefig("img/track.pdf")
        plt.show()

    def save_csv(self, filename, hdr=None):
        """Save track as a csv file along with tags: blue, yellow or big

        Args:
            file_path (str): the name and path of the file to save
            hdr (str): header of the CSV file

        Returns:
            Nothing
        """

        # if hdr is None:
        #     print("Please give me a header as a string. Exitting...")
        #     return

        if filename.find(".csv") == -1:
            filename = filename + ".csv"

        df = pd.DataFrame(columns=["tag", "x", "y"])

        # assuming there always are blue and yellow cones
        df["x"] = np.hstack((self.blue_cones[:, 0], self.yellow_cones[:, 0]))
        df["y"] = np.hstack((self.blue_cones[:, 1], self.yellow_cones[:, 1]))
        df["tag"].iloc[:] = "blue"
        df["tag"].iloc[-self.yellow_cones.shape[0]:] = "yellow"

        if self.big_orange_cones is not None:
            empty = pd.DataFrame(np.nan, index=np.arange(self.big_orange_cones.shape[0]), columns=["tag", "x", "y"])
            df = df.append(empty)
            df["x"] = np.hstack((df["x"].dropna().values, self.big_orange_cones[:, 0]))
            df["y"] = np.hstack((df["y"].dropna().values, self.big_orange_cones[:, 1]))
            df["tag"].iloc[-self.big_orange_cones.shape[0]:] = "big_orange"

        if self.orange_cones is not None:
            empty = pd.DataFrame(np.nan, index=np.arange(self.orange_cones.shape[0]), columns=["tag", "x", "y"])
            df = df.append(empty)
            df["x"] = np.hstack((df["x"].dropna().values, self.orange_cones[:, 0]))
            df["y"] = np.hstack((df["y"].dropna().values, self.orange_cones[:, 1]))
            df["tag"].iloc[-self.orange_cones.shape[0]:] = "orange"

        if self.midpoints is not None:
            empty = pd.DataFrame(np.nan, index=np.arange(self.midpoints.shape[0]), columns=["tag", "x", "y"])
            df = df.append(empty)
            df["x"] = np.hstack((df["x"].dropna().values, self.midpoints[:, 0]))
            df["y"] = np.hstack((df["y"].dropna().values, self.midpoints[:, 1]))
            df["tag"].iloc[-self.midpoints.shape[0]:] = "midpoint"

        df.to_csv(filename, index=False)

        print("Succesfully saved to csv")

    def save_sdf(self, model_name):
        cone_meshes = {"yellow": "model://models/yellow_cone",
                "blue": "model://models/blue_cone",
                "big": "model://models/big_cone",
                "orange":"model://models/cone"}

        root = Element("sdf")
        root.set("version", "1.6")
        model = SubElement(root, "model")
        model.set("name", model_name)

        # deal with blue cones
        for i, each in enumerate(self.blue_cones):
            include = SubElement(model, "include")
            uri = SubElement(include, "uri")
            uri.text = cone_meshes["blue"]
            pose = SubElement(include, "pose")
            pose.text = str(each[0]) + " " + str(each[1]) + " 0 0 0 0"
            name = SubElement(include, "name")
            name.text = "blue_cone_" + str(i)

        # deal with yellow cones
        for i, each in enumerate(self.yellow_cones):
            include = SubElement(model, "include")
            uri = SubElement(include, "uri")
            uri.text = cone_meshes["yellow"]
            pose = SubElement(include, "pose")
            pose.text = str(each[0]) + " " + str(each[1]) + " 0 0 0 0"
            name = SubElement(include, "name")
            name.text = "yellow_cone_" + str(i)

        # deal with big cones
        for i, each in enumerate(self.big_orange_cones):
            include = SubElement(model, "include")
            uri = SubElement(include, "uri")
            uri.text = cone_meshes["big"]
            pose = SubElement(include, "pose")
            pose.text = str(each[0]) + " " + str(each[1]) + " 0 0 0 0"
            name = SubElement(include, "name")
            name.text = "big_cone_" + str(i)

        tree = ET.ElementTree(root)

        xmlstr = minidom.parseString(ET.tostring(root)).toprettyxml(indent="   ")

        with open("model.sdf", "w") as f:
            f.write(xmlstr)
        print("Created SDF file successfully!")

    def remove_point(self, p, ps):
        """Removes a point from a numpy array

        Args:
            p (2D-point): point to remove
            ps (2D numpy array): points to remove from

        Returns:
            Numpy array with point p removed
        """
        points = ps[np.all(ps != p, 1), :]
        return points

    def find_closest(self, p, ps):
        """Find the closes point to p from points ps

        Args:
            p (2D-point): source point
            ps (2D numpy array): array of target points

        Returns:
            [x,y] of the closest point
            distance to the closest point
        """
        # drop the point if in points
        points = self.remove_point(p, ps)
        dist_2 = np.sum((points - p)**2, axis=1)
        return points[np.argmin(dist_2), :], np.min(dist_2)

    def plot_line(self, a, b, marker_style="ro-"):
        plt.plot([a[0], b[0]], [a[1], b[1]], marker_style)

    # Smooth the line ana generated nice and uniform waypoints
    def smoothLine(self, points, mul=5):
        """Centerline is 2xN (x y coordinates of midpoints) np array
            close_track (Connect first and last point)
            track limit track widtd
        """
        tck, u = interpolate.splprep(points.T, u=None, s=1.0, per=True)
        linargs = np.linspace(u.min(), u.max(), mul * points.shape[0])
        x_i, y_i = interpolate.splev(linargs, tck)
        output = np.array((x_i, y_i)).T
        return output

    def order_points(self, points):
        """Order points based on closest next point

        Args:
            points (2D numpy array): points to order

        Returns:
            Numpy array with point p removed
        """
        ordered = []
        current_point = points[0]
        points = points[1:]
        ordered.append(current_point)

        while points.shape[0] is not 0:
            i, d = self.find_closest(current_point, points)
            ordered.append(i)
            points = self.remove_point(i, points)
            current_point = i

        ordered.append(current_point)

        return np.array(ordered)

    def rotate_origin_only(self, xy, radians):
        """Only rotate a point around the origin (0, 0)."""
        x = xy[:, 0]
        y = xy[:, 1]
        xx = x * np.cos(radians) + y * np.sin(radians)
        yy = -x * np.sin(radians) + y * np.cos(radians)

        out = np.vstack((xx, yy))
        return out.T

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generates a CSV file of cone\
                                     locations based on the SDF Gazebo models")
    parser.add_argument('track_name', metavar='track_name', type=str,
                        help="the name of the Gazebo model track")
    parser.add_argument('--midpoints', metavar='midpoints', type=bool, default=False,
                        help="If true, midpoints will be generated and saved in the CSV")

    args = parser.parse_args()
    d = os.path.abspath(__file__)
    home = os.path.dirname(os.path.dirname(os.path.dirname(d)))
    track_path = os.path.join(home, "eufs_description", "models",
                              args.track_name, "model.sdf")

    # check if eufs_description exists
    try:
        assert os.path.isdir(os.path.join(home, "eufs_description"))
    except:
        raise(AssertionError(("Can't find eufs_description directory."
              "it is in the same location as eufs_gazebo!")))

    # check if requested track exists
    try:
        assert os.path.exists(track_path)
    except:
        raise(AssertionError(("Can't find track called {} make sure that it is"
              "within eufs_description/models/".format(args.track_name))))

    track = Track()
    track.load_sdf(track_path)
    if args.midpoints:
        track.generate_midpoints()
        track.generate_tracks()
    track.save_csv(args.track_name)
