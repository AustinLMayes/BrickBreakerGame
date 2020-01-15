import copy
import math
import tkinter as tk
import requests
import sys
import random

# Main game class
class Game(tk.Canvas):
    # If the game is showing text to the user
    SHOWING_TEXT = False
    linesNb = 20
    seconds = 0

    # Bar properties
    BAR_HEIGHT = 20
    BAR_FRICTION = 10

    # If the game has been started
    STARTED=False

    # Ball property
    BALL_SPEED = 7

    # Bricks properties
    BRICKS = []
    BRICK_WIDTH = 50
    BRICK_HEIGHT = 20
    BRICKS_PER_LINE = 16
    # Map of color code -> color
    COLOR_MAPPING = {
        "r": "#8c0e0e",
        "g": "#168e0e",
        "b": "#0e1991",
        "t": "#0d9664",
        "p": "#6a0d99",
        "y": "#ffff00",
        "o": "#dd940b",
    }

    # Screen properties
    SCREEN_HEIGHT = 500
    SCREEN_WIDTH = BRICK_WIDTH * BRICKS_PER_LINE

    # Cached API properties
    ip = ""
    API_URL = "http://localhost:8080/"
    level_prefix = ''

    # This method initializes some attributes: the ball, the bar...
    def __init__(self, root):
        tk.Canvas.__init__(self, root, bg="#000000", bd=0, highlightthickness=0, relief="ridge",
                           width=self.SCREEN_WIDTH,
                           height=self.SCREEN_HEIGHT)
        self.pack()
        self.timeContainer = self.create_text(self.SCREEN_WIDTH * 4 / 5, self.SCREEN_HEIGHT * 12 / 13, text="00:00:00",
                                              fill="#cccccc", font=("Arial", 30), justify="center")
        # Cache machine IP
        self.ip = requests.get('https://api.ipify.org').text
        # If not blacklisted, load game
        if not self.check_blacklisted():
            self.shieldVisible = self.create_rectangle(0, 0, 0, 0, width=0)
            self.bar = self.create_rectangle(0, 0, 0, 0, fill="#7f8c8d", width=0)
            self.ball = self.create_oval(0, 0, 0, 0, width=0)
            self.ballNext = self.create_oval(0, 0, 0, 0, width=0, state="hidden")
            self.pick_random_level()
            self.load_level(1)
            self.tick()

    # Pick a random level prefix from the API
    def pick_random_level(self):
        try:
            groups = self.api_request("levels/groups", json=True)
            self.level_prefix = random.choice(groups)
        except:
            self.render_text("An unknown error has occurred.", hide=False)

    # Determine if the player's IP is blacklisted
    def check_blacklisted(self):
        try:
            reason = self.api_request("blacklist/check", {"ip": self.ip})
            if reason:
                self.render_text("Your IP address is banned: " + reason, delay=10000, callback=lambda: sys.exit(0))
                return True
        except:
            self.render_text("An unknown error has occurred.", hide=False)
        return False

    # This method, called each time a level is loaded or reloaded,
    # resets all the elements properties (size, position...).
    def reset(self):
        self.barWidth = 100
        self.ballRadius = 7
        self.coords(self.shieldVisible, (0, self.SCREEN_HEIGHT - 5, self.SCREEN_WIDTH, self.SCREEN_HEIGHT))
        self.itemconfig(self.shieldVisible, fill=self.COLOR_MAPPING["b"], state="hidden")
        self.coords(self.bar, ((self.SCREEN_WIDTH - self.barWidth) / 2, self.SCREEN_HEIGHT - self.BAR_HEIGHT,
                               (self.SCREEN_WIDTH + self.barWidth) / 2, self.SCREEN_HEIGHT))
        self.coords(self.ball, (
            self.SCREEN_WIDTH / 2 - self.ballRadius, self.SCREEN_HEIGHT - self.BAR_HEIGHT - 2 * self.ballRadius,
            self.SCREEN_WIDTH / 2 + self.ballRadius, self.SCREEN_HEIGHT - self.BAR_HEIGHT))
        self.itemconfig(self.ball, fill="#2c3e50")
        self.coords(self.ballNext, tk._flatten(self.coords(self.ball)))
        # Ball effects
        self.effects = {
            "ball.onFire": [0, 0],
            "bar.isTall": [0, 0],
            "ball.isTall": [0, 0],
            "shield.visible": [0, -1],
        }
        self.lastKnownEffectsState = copy.deepcopy(self.effects)
        self.ballInPlay = False
        self.keyPressed = [False, False]
        self.gameFailed = False
        self.gameSucceeded = False
        self.ballAngle = math.radians(90)
        for brick in self.BRICKS:
            self.delete(brick)
            del brick

    # Load a level
    def load_level(self, level):
        self.reset()
        self.levelNum = level
        self.BRICKS = []
        try:
            lvl = self.api_request("levels/search", data={"name": self.level_prefix + "-" + level.__str__()}, json=True)
            content = list(lvl['contents'].replace("\r\n", ""))[:(self.BRICKS_PER_LINE * self.linesNb)]
            for i, el in enumerate(content):
                col = i % self.BRICKS_PER_LINE
                line = i // self.BRICKS_PER_LINE
                if el != ".":
                    self.BRICKS.append(self.create_rectangle(col * self.BRICK_WIDTH, line * self.BRICK_HEIGHT,
                                                             (col + 1) * self.BRICK_WIDTH,
                                                             (line + 1) * self.BRICK_HEIGHT, fill=self.COLOR_MAPPING[el],
                                                             width=2, outline="#000000"))
        except:
            if self.seconds == 0:
                # API is down?
                self.render_text("An unknown error has occurred.", hide=False)
            else:
                self.render_text("GAME ENDED IN\n" + "%02d mn %02d sec %02d" % (
                int(self.seconds) // 60, int(self.seconds) % 60, (self.seconds * 100) % 100), hide=False)
            return
        self.render_text(lvl['name'].replace("-" + str(level), "") + " by " + lvl['creator'] + "\n" + lvl['desc'] +
                         "\n TIER: " + str(level))

    # This method, called each 1/60 of second, computes again
    # the properties of all elements (positions, collisions, effects...).
    def tick(self):
        if self.ballInPlay and not (self.SHOWING_TEXT):
            self.tick_ball()
            self.tick_time()

        self.tick_effects()

        if self.keyPressed[0]:
            self.tick_bar(-game.BAR_FRICTION)
        elif self.keyPressed[1]:
            self.tick_bar(game.BAR_FRICTION)

        if not (self.SHOWING_TEXT):
            if self.gameSucceeded:
                self.render_text("You won!", callback=lambda: self.load_level(self.levelNum + 1))
            elif self.gameFailed:
                self.render_text("You lost! :(", callback=lambda: self.load_level(self.levelNum))

        self.after(int(1000 / 60), self.tick)

    # Called on each game tick to move the bar a certain direction
    def tick_bar(self, x):
        barCoords = self.coords(self.bar)
        if barCoords[0] < 10 and x < 0:
            x = -barCoords[0]
        elif barCoords[2] > self.SCREEN_WIDTH - 10 and x > 0:
            x = self.SCREEN_WIDTH - barCoords[2]

        self.move(self.bar, x, 0)
        if not (self.ballInPlay):
            self.move(self.ball, x, 0)

    # This method, called at each frame, moves the ball.
    # It computes:
    #     - collisions between ball and bricks/bar/edge of screen
    #     - next ball position using "ballAngle" and "BALL_SPEED" attributes
    #     - effects to the ball and the bar during collision with special bricks
    def tick_ball(self):
        self.move(self.ballNext, self.BALL_SPEED * math.cos(self.ballAngle),
                  -self.BALL_SPEED * math.sin(self.ballAngle))
        ballNextCoords = self.coords(self.ballNext)

        # Collisions computation between ball and bricks
        i = 0
        while i < len(self.BRICKS):
            collision = self.collision(self.ball, self.BRICKS[i])
            collisionNext = self.collision(self.ballNext, self.BRICKS[i])
            if not collisionNext:
                brickColor = self.itemcget(self.BRICKS[i], "fill")
                # "bar.isTall" effect (green bricks)
                if brickColor == self.COLOR_MAPPING["g"]:
                    self.effects["bar.isTall"][0] = 1
                    self.effects["bar.isTall"][1] = 240
                # "shield.visible" effect (blue bricks)
                elif brickColor == self.COLOR_MAPPING["b"]:
                    self.effects["shield.visible"][0] = 1
                # "ball.onFire" effect (purple bricks)
                elif brickColor == self.COLOR_MAPPING["y"]:
                    self.effects["ball.onFire"][0] += 1
                    self.effects["ball.onFire"][1] = 240
                # "ball.isTall" effect (turquoise bricks)
                elif brickColor == self.COLOR_MAPPING["t"]:
                    self.effects["ball.isTall"][0] = 1
                    self.effects["ball.isTall"][1] = 240

                if not (self.effects["ball.onFire"][0]):
                    if collision == 1 or collision == 3:
                        self.ballAngle = math.radians(180) - self.ballAngle
                    if collision == 2 or collision == 4:
                        self.ballAngle = -self.ballAngle

                # If the brick is red, it becomes orange.
                if brickColor == self.COLOR_MAPPING["r"]:
                    self.itemconfig(self.BRICKS[i], fill=self.COLOR_MAPPING["o"])
                # If the brick is orange, it becomes yellow.
                elif brickColor == self.COLOR_MAPPING["o"]:
                    self.itemconfig(self.BRICKS[i], fill=self.COLOR_MAPPING["y"])
                # If the brick is yellow (or an other color except red/orange), it is destroyed.
                else:
                    self.delete(self.BRICKS[i])
                    del self.BRICKS[i]
            i += 1

        self.gameSucceeded = len(self.BRICKS) == 0

        # Collisions computation between ball and edge of screen
        if ballNextCoords[0] < 0 or ballNextCoords[2] > self.SCREEN_WIDTH:
            self.ballAngle = math.radians(180) - self.ballAngle
        elif ballNextCoords[1] < 0:
            self.ballAngle = -self.ballAngle
        elif not (self.collision(self.ballNext, self.bar)):
            ballCenter = self.coords(self.ball)[0] + self.ballRadius
            barCenter = self.coords(self.bar)[0] + self.barWidth / 2
            angleX = ballCenter - barCenter
            angleOrigin = (-self.ballAngle) % (3.14159 * 2)
            angleComputed = math.radians(-70 / (self.barWidth / 2) * angleX + 90)
            self.ballAngle = (1 - (abs(angleX) / (self.barWidth / 2)) ** 0.25) * angleOrigin + (
                    (abs(angleX) / (self.barWidth / 2)) ** 0.25) * angleComputed
        elif not (self.collision(self.ballNext, self.shieldVisible)):
            if self.effects["shield.visible"][0]:
                self.ballAngle = -self.ballAngle
                self.effects["shield.visible"][0] = 0
            else:
                self.gameFailed = True

        self.move(self.ball, self.BALL_SPEED * math.cos(self.ballAngle), -self.BALL_SPEED * math.sin(self.ballAngle))
        self.coords(self.ballNext, tk._flatten(self.coords(self.ball)))

    # Tick currently active effects
    def tick_effects(self):
        for key in self.effects.keys():
            if self.effects[key][1] > 0:
                self.effects[key][1] -= 1
            if self.effects[key][1] == 0:
                self.effects[key][0] = 0

        # "ball.onFire" effect allows the ball to destroy bricks without bouncing on them.
        if self.effects["ball.onFire"][0]:
            self.itemconfig(self.ball, fill=self.COLOR_MAPPING["y"])
        else:
            self.itemconfig(self.ball, fill="#ffffff")

        # "bar.isTall" effect increases the bar size.
        if self.effects["bar.isTall"][0] != self.lastKnownEffectsState["bar.isTall"][0]:
            diff = self.effects["bar.isTall"][0] - self.lastKnownEffectsState["bar.isTall"][0]
            self.barWidth += diff * 60
            coords = self.coords(self.bar)
            self.coords(self.bar, tk._flatten((coords[0] - diff * 30, coords[1], coords[2] + diff * 30, coords[3])))
        # "ball.isTall" effect increases the ball size.
        if self.effects["ball.isTall"][0] != self.lastKnownEffectsState["ball.isTall"][0]:
            diff = self.effects["ball.isTall"][0] - self.lastKnownEffectsState["ball.isTall"][0]
            self.ballRadius += diff * 10
            coords = self.coords(self.ball)
            self.coords(self.ball, tk._flatten(
                (coords[0] - diff * 10, coords[1] - diff * 10, coords[2] + diff * 10, coords[3] + diff * 10)))

        # "shield.visible" effect allows the ball to bounce once
        # at the bottom of the screen (it's like an additional life).
        if self.effects["shield.visible"][0]:
            self.itemconfig(self.shieldVisible, fill=self.COLOR_MAPPING["b"], state="normal")
        else:
            self.itemconfig(self.shieldVisible, state="hidden")

        self.lastKnownEffectsState = copy.deepcopy(self.effects)

    # This method updates game time (displayed in the background).
    def tick_time(self):
        self.seconds += 1 / 60
        self.itemconfig(self.timeContainer, text="%02d:%02d:%02d" % (
            int(self.seconds) // 60, int(self.seconds) % 60, (self.seconds * 100) % 100))

    # This method displays some text.
    def render_text(self, text, hide=True, callback=None, delay=3000):
        self.SHOWING_TEXT = True
        self.textContainer = self.create_rectangle(0, 0, self.SCREEN_WIDTH, self.SCREEN_HEIGHT, fill="#000000", width=0,
                                                   stipple="gray50")
        self.text = self.create_text(self.SCREEN_WIDTH / 2, self.SCREEN_HEIGHT / 2, text=text, fill="#ffffff", font=("Arial", 25),
                                     justify="center")
        if hide:
            self.after(delay, self.hide_text)
        if callback != None:
            self.after(delay, callback)

    # This method deletes the text display.
    def hide_text(self):
        self.SHOWING_TEXT = False
        self.delete(self.textContainer)
        self.delete(self.text)

    # This method computes the relative position of 2 objects that is collisions.
    def collision(self, el1, el2):
        collisionCounter = 0

        objectCoords = self.coords(el1)
        obstacleCoords = self.coords(el2)

        if objectCoords[2] < obstacleCoords[0] + 5:
            collisionCounter = 1
        if objectCoords[3] < obstacleCoords[1] + 5:
            collisionCounter = 2
        if objectCoords[0] > obstacleCoords[2] - 5:
            collisionCounter = 3
        if objectCoords[1] > obstacleCoords[3] - 5:
            collisionCounter = 4

        return collisionCounter

    def api_request(self, endpoint, data=None, json=False):
        if data is None:
            data = {}
        res = requests.get(self.API_URL + endpoint, params=data)
        if json:
            return res.json()
        else:
            return res.text


# This function is called on key down.
def on_press(event):
    global game, hasEvent

    if event.keysym == "Left":
        game.keyPressed[0] = 1
    elif event.keysym == "Right":
        game.keyPressed[1] = 1
    elif event.keysym == "space" and not (game.SHOWING_TEXT):
        game.ballInPlay = True


# This function is called on key up.
def on_release(event):
    global game, hasEvent

    if event.keysym == "Left":
        game.keyPressed[0] = 0
    elif event.keysym == "Right":
        game.keyPressed[1] = 0


# Initialization of the window
root = tk.Tk()
root.title("Brick Breaker")
root.resizable(0, 0)
root.bind("<Key>", on_press)
root.bind("<KeyRelease>", on_release)

# Starting up of the game
game = Game(root)
root.mainloop()
