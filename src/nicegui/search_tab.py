import asyncio
import base64
import cairosvg
import io

from nicegui import ui, events
from nicegui.events import KeyEventArguments, MouseEventArguments
from google.cloud import vision
from PIL import Image


# idea from https://www.reddit.com/r/nicegui/comments/1g21jtp/uiinteractive_creating_a_drawing_canvas_that/
# i only use mouse anyways, so this shouldnt be an issue
class SearchTab(ui.element):
    def __init__(self, srs_app):
        super().__init__()

        self.srs_app = srs_app
        self.vision_client = vision.ImageAnnotatorClient()

        self.draw_area = ui.interactive_image(
            size = (100, 100),
            on_mouse = self.handle_mouse,
            events = ["mousedown", "mousemove", "mouseup"],
            cross = False
        ).classes("w-full bg-slate-100").props('id=draw-canvas')

        self.keyboard = ui.keyboard(on_key = self.handle_key)

        self.clear_button = ui.button("Clear Drawing", color = "primary", on_click = lambda: self.clear_strokes())
        self.predict_button = ui.button("Predict", color = "primary", on_click = lambda: self.predict())

        self.prediction_label = ui.label("Click the predict button!")

        self.draw_area.signature_path = ""
        self.draw_area.is_drawing = None

        self.draw_color = "Black"
        self.draw_stroke_width = 1
        self.strokes = []

        self.canvas_x_offset = 65
        self.canvas_size = (225, 160)

    async def predict(self):
        res = []
        image = await ui.run_javascript(f"""
            return new Promise((resolve) => {{
                const draw_element = document.querySelector('#draw-canvas');
                const svg = draw_element.querySelector('svg');

                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
    
                ctx.fillStyle = 'white';
                ctx.fillRect({self.canvas_x_offset}, 0, {self.canvas_size[1]}, {self.canvas_size[0]});
                
                const svg_data = new XMLSerializer().serializeToString(svg);
                const svg_data_url = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svg_data)));
                
                const img = new Image();
                img.onload = function() {{
                    ctx.drawImage(img, 0, 0);
                    resolve(canvas.toDataURL('image/png'));
                }};
                
                img.src = svg_data_url;
            }});
        """)

        image_base64 = image.split(",")[1]
        image_bytes = base64.b64decode(image_base64)

        vision_image = vision.Image(content = image_bytes)
        text_response = self.vision_client.text_detection(image = vision_image)

        if text_response.text_annotations:
            detected_text = text_response.text_annotations[0].description.strip()
            res.append(detected_text)

        self.prediction_label.text = " ".join(res)
        
    def get_current_stroke(self):
        current_stroke = f"<path d='{self.draw_area.signature_path}' stroke='{self.draw_color}' stroke-width='{self.draw_stroke_width}' fill='none' />"

        return current_stroke

    def clear_strokes(self):
        self.strokes = []
        self.draw_area.content = " ".join(self.strokes)

        return None

    # "helper" function for keypresses
    def handle_key(self, e: KeyEventArguments) -> None:
        key = e.key
        key_str = str(key)

        # use "keydown"; otherwise we get 2 keys per press
        if e.action.keydown:
            match key:

                # if ctrl + z, remove last stroke
                case "z" if e.modifiers.ctrl:
                    self.strokes.pop()
                    self.draw_area.content = " ".join(self.strokes)

                case "s" if e.modifiers.ctrl:
                    ui.run_javascript(f"""
                        const draw_element = document.querySelector('#draw-canvas');
                        const svg = draw_element.querySelector('svg');
            
                        const canvas = document.createElement('canvas');
                        const ctx = canvas.getContext('2d');
            
                        ctx.fillStyle = 'white';
                        ctx.fillRect({self.canvas_x_offset}, 0, {self.canvas_size[1]}, {self.canvas_size[0]});
            
                        const svg_data = new XMLSerializer().serializeToString(svg);
                        const svg_blob = new Blob([svg_data], {{type: 'image/svg+xml;charset=utf-8'}});
                        const svg_url = URL.createObjectURL(svg_blob);
            
                        const img = new Image();
                        img.onload = function() {{
                            ctx.drawImage(img, 0, 0);
            
                            const link = document.createElement('a');
                            link.download = 'drawing.png';
                            link.href = canvas.toDataURL('image/png');
                            link.click();
            
                        }};
            
                        img.src = svg_url;
                    """)

        return None

    def handle_mouse(self, e: MouseEventArguments):

        match e.type:

            # Start a new path
            case "mousedown":
                self.draw_area.is_drawing = True
                self.draw_area.signature_path = f"M {e.image_x} {e.image_y}"

            # Add to the path while moving
            case "mousemove" if self.draw_area.is_drawing:
                self.draw_area.signature_path += f"L {e.image_x} {e.image_y}"
    
                # Show the live drawing by combining all previous paths + current one
                self.draw_area.content = f"{self.draw_area.content}{self.get_current_stroke()}"

            # Finalize the current path and append it to ii.content
            case "mouseup":
                self.draw_area.is_drawing = False  
                self.draw_area.content += self.get_current_stroke()
                self.strokes.append(self.draw_area.content)
    
                # Reset the path for the next drawing
                self.draw_area.signature_path = ""