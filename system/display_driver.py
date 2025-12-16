import smbus2
from .log_utils import debug, info, warn, error
from PIL import Image, ImageDraw, ImageFont

# ----------------------------------------------------------------------
# Global configuration
# ----------------------------------------------------------------------
I2C_PORT        = 3
OLED_ADDRS      = {0x3C, 0x3D}                # SH1106 / SSD1306 / SSD1315
LCD_ADDRS       = {0x27, 0x3F, 0x20, 0x21}    # PCF8574 / PCF8574A variants
LCD_ROWS        = 4                           # number of text rows
LCD_COLS        = 20                          # character columns per line
FONT_PATH       = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SIZE       = 11                          # for OLED rendering
OLED_LINE_SPACING = 16                        # pixel offset between text rows
# ----------------------------------------------------------------------

class DisplayDriver:
    def __init__(self, i2c_port=I2C_PORT):
        self.i2c_port = i2c_port
        self.oled = None
        self.lcd = None
        self.last_oled_frame = None
        self.last_lcd_lines = ["" for _ in range(LCD_ROWS)]
        self._detect_and_init()

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def _detect_and_init(self):
        bus = smbus2.SMBus(self.i2c_port)
        found = []
        for addr in sorted(OLED_ADDRS | LCD_ADDRS):
            try:
                bus.write_quick(addr)
                found.append(addr)
            except OSError:
                pass
        bus.close()

        # --- OLED detection -------------------------------------------
        for addr in OLED_ADDRS:
            if addr in found:
                try:
                    from luma.core.interface.serial import i2c
                    from luma.oled.device import sh1106, ssd1306
                    serial = i2c(port=self.i2c_port, address=addr)
                    try:
                        self.oled = sh1106(serial)
                        debug(f"✅ SH1106 OLED initialized at 0x{addr:02X}")
                    except Exception:
                        self.oled = ssd1306(serial)
                        debug(f"✅ SSD1306 OLED initialized at 0x{addr:02X}")
                    break
                except Exception as e:
                    warn(f"⚠️ OLED init failed: {e}")

        # --- LCD detection --------------------------------------------
        for addr in LCD_ADDRS:
            if addr in found:
                try:
                    from RPLCD.i2c import CharLCD
                    self.lcd = CharLCD('PCF8574', addr,
                                       port=self.i2c_port,
                                       cols=LCD_COLS,
                                       rows=LCD_ROWS)
                    debug(f"✅ HD44780 LCD initialized at 0x{addr:02X}")
                    break
                except Exception as e:
                    warn(f"⚠️ LCD init failed: {e}")

        if not self.oled and not self.lcd:
            warn("⚠️ No display found on I2C bus.")
        else:
            active = []
            if self.oled: active.append("OLED")
            if self.lcd:  active.append("LCD")
            info(f"[DisplayDriver] Active: {', '.join(active)}")

    # ------------------------------------------------------------------
    def clear(self):
        """Clear both displays and reset frame cache."""
        if self.oled:
            img = Image.new("1", (self.oled.width, self.oled.height))
            self.oled.display(img)
            self.last_oled_frame = None
        if self.lcd:
            self.lcd.clear()
            self.last_lcd_lines = ["" for _ in range(LCD_ROWS)]

    # ------------------------------------------------------------------
    def draw_text_lines(self, lines):
        """Update both displays; LCD per-line diff, OLED full-frame diff."""
        if not lines:
            return

        # --- LCD incremental update -----------------------------------
        if self.lcd:
            try:
                for i in range(min(LCD_ROWS, len(lines))):
                    new = lines[i][:LCD_COLS]
                    if new != self.last_lcd_lines[i]:
                        self.lcd.cursor_pos = (i, 0)
                        self.lcd.write_string(new.ljust(LCD_COLS))
                        self.last_lcd_lines[i] = new
            except OSError as e:
                warn(f"[LCD] update failed: {e}")

        # --- OLED full-frame refresh ----------------------------------
        if self.oled:
            joined = "\n".join(lines[:LCD_ROWS])
            if joined != self.last_oled_frame:
                try:
                    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
                    img = Image.new("1", (self.oled.width, self.oled.height))
                    draw = ImageDraw.Draw(img)
                    for i, line in enumerate(lines[:LCD_ROWS]):
                        draw.text((0, i * OLED_LINE_SPACING), line, font=font, fill=255)
                    self.oled.display(img)
                    self.last_oled_frame = joined
                except OSError as e:
                    warn(f"[OLED] update failed: {e}")
