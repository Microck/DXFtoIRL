import ezdxf
from ezdxf import bbox
from ezdxf.math import BoundingBox
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import sys
import os
import math

# --- Configuration ---
PAGE_WIDTH_PT, PAGE_HEIGHT_PT = landscape(A4)
POINTS_PER_MM = mm / 1.0
DEFAULT_LINE_WIDTH = 0.3  # Thicker line for better visibility
# --- End Configuration ---


def get_modelspace_extents(doc) -> BoundingBox | None:
    """Calculate the bounding box of the modelspace entities using ezdxf.bbox."""
    msp = doc.modelspace()
    try:
        overall_bbox = bbox.extents(msp, fast=False)
        if overall_bbox.has_data:
            return overall_bbox
        else:
            print("DEBUG: Warning - ezdxf.bbox.extents() did not find valid data.")
            return None
    except Exception as e:
        print(f"DEBUG: Error calculating extents using ezdxf.bbox: {e}")
        return None


def draw_entity_on_pdf(entity, pdf_canvas, offset_x_pt, offset_y_pt, scale_pt_per_mm):
    """Draws DXF entities directly onto the PDF canvas."""
    try:
        # Set default properties for each entity
        pdf_canvas.setLineWidth(DEFAULT_LINE_WIDTH)
        pdf_canvas.setStrokeColorRGB(0, 0, 0)
        pdf_canvas.setFillColorRGB(0, 0, 0)

        drawn = False
        entity_type = entity.dxftype()
        
        if entity_type == "LINE":
            start = entity.dxf.start
            end = entity.dxf.end
            x1 = (start.x * scale_pt_per_mm) + offset_x_pt
            y1 = (start.y * scale_pt_per_mm) + offset_y_pt
            x2 = (end.x * scale_pt_per_mm) + offset_x_pt
            y2 = (end.y * scale_pt_per_mm) + offset_y_pt
            pdf_canvas.line(x1, y1, x2, y2)
            drawn = True
        
        elif entity_type == "CIRCLE":
            center = entity.dxf.center
            radius = entity.dxf.radius
            cx = (center.x * scale_pt_per_mm) + offset_x_pt
            cy = (center.y * scale_pt_per_mm) + offset_y_pt
            r = radius * scale_pt_per_mm
            pdf_canvas.circle(cx, cy, r, stroke=1, fill=0)
            drawn = True
        
        elif entity_type == "ARC":
            center = entity.dxf.center
            radius = entity.dxf.radius
            start_angle = entity.dxf.start_angle
            end_angle = entity.dxf.end_angle
            delta_angle = end_angle - start_angle
            if delta_angle < 0:
                delta_angle += 360
            cx = (center.x * scale_pt_per_mm) + offset_x_pt
            cy = (center.y * scale_pt_per_mm) + offset_y_pt
            r = radius * scale_pt_per_mm
            x1, y1 = cx - r, cy - r
            x2, y2 = cx + r, cy + r
            pdf_canvas.arc(x1, y1, x2, y2, start_angle, delta_angle)
            drawn = True
        
        elif entity_type == "LWPOLYLINE":
            # Improved LWPOLYLINE handler
            if hasattr(entity, 'get_points'):
                # Get points directly if possible
                points = entity.get_points('xy')
                
                if len(points) > 1:
                    pdf_path = pdf_canvas.beginPath()
                    first_point = points[0]
                    pdf_path.moveTo(
                        (first_point[0] * scale_pt_per_mm) + offset_x_pt,
                        (first_point[1] * scale_pt_per_mm) + offset_y_pt
                    )
                    
                    for point in points[1:]:
                        pdf_path.lineTo(
                            (point[0] * scale_pt_per_mm) + offset_x_pt,
                            (point[1] * scale_pt_per_mm) + offset_y_pt
                        )
                    
                    # Check if the polyline is closed
                    if hasattr(entity, 'closed') and entity.closed:
                        pdf_path.close()
                    elif hasattr(entity, 'is_closed') and entity.is_closed:
                        pdf_path.close()
                    
                    pdf_canvas.drawPath(pdf_path, stroke=1, fill=0)
                    drawn = True
            
            # Alternative approach if get_points fails
            elif hasattr(entity, 'vertices'):
                vertices = list(entity.vertices())
                if len(vertices) > 1:
                    pdf_path = pdf_canvas.beginPath()
                    first_vertex = vertices[0]
                    pdf_path.moveTo(
                        (first_vertex[0] * scale_pt_per_mm) + offset_x_pt,
                        (first_vertex[1] * scale_pt_per_mm) + offset_y_pt
                    )
                    
                    for vertex in vertices[1:]:
                        pdf_path.lineTo(
                            (vertex[0] * scale_pt_per_mm) + offset_x_pt,
                            (vertex[1] * scale_pt_per_mm) + offset_y_pt
                        )
                    
                    # Check for closure
                    if hasattr(entity, 'closed') and entity.closed:
                        pdf_path.close()
                    
                    pdf_canvas.drawPath(pdf_path, stroke=1, fill=0)
                    drawn = True
        
        elif entity_type == "POLYLINE":
            # Handle old-style POLYLINE entities
            if hasattr(entity, 'vertices'):
                vertices = list(entity.vertices())
                if len(vertices) > 1:
                    pdf_path = pdf_canvas.beginPath()
                    first_vertex = vertices[0].dxf.location
                    pdf_path.moveTo(
                        (first_vertex.x * scale_pt_per_mm) + offset_x_pt,
                        (first_vertex.y * scale_pt_per_mm) + offset_y_pt
                    )
                    
                    for vertex in vertices[1:]:
                        point = vertex.dxf.location
                        pdf_path.lineTo(
                            (point.x * scale_pt_per_mm) + offset_x_pt,
                            (point.y * scale_pt_per_mm) + offset_y_pt
                        )
                    
                    # Check if polyline is closed
                    if hasattr(entity, 'is_closed') and entity.is_closed:
                        pdf_path.close()
                    
                    pdf_canvas.drawPath(pdf_path, stroke=1, fill=0)
                    drawn = True
        
        elif entity_type == "SPLINE":
            # Handle SPLINE entities by flattening to line segments
            if hasattr(entity, 'flattening'):
                points = list(entity.flattening(distance=0.1))  # Smaller distance = more precision
                if len(points) > 1:
                    pdf_path = pdf_canvas.beginPath()
                    first_point = points[0]
                    pdf_path.moveTo(
                        (first_point.x * scale_pt_per_mm) + offset_x_pt,
                        (first_point.y * scale_pt_per_mm) + offset_y_pt
                    )
                    
                    for point in points[1:]:
                        pdf_path.lineTo(
                            (point.x * scale_pt_per_mm) + offset_x_pt,
                            (point.y * scale_pt_per_mm) + offset_y_pt
                        )
                    
                    # Close if it's a closed spline
                    if hasattr(entity, 'closed') and entity.closed:
                        pdf_path.close()
                    
                    pdf_canvas.drawPath(pdf_path, stroke=1, fill=0)
                    drawn = True
        
        elif entity_type == "ELLIPSE":
            # Handle ELLIPSE entities by flattening to line segments
            if hasattr(entity, 'vertices'):
                vertices = list(entity.vertices(num=60))  # More points = smoother curve
                if len(vertices) > 1:
                    pdf_path = pdf_canvas.beginPath()
                    first_point = vertices[0]
                    pdf_path.moveTo(
                        (first_point.x * scale_pt_per_mm) + offset_x_pt,
                        (first_point.y * scale_pt_per_mm) + offset_y_pt
                    )
                    
                    for point in vertices[1:]:
                        pdf_path.lineTo(
                            (point.x * scale_pt_per_mm) + offset_x_pt,
                            (point.y * scale_pt_per_mm) + offset_y_pt
                        )
                    
                    pdf_path.close()  # Ellipses are always closed
                    pdf_canvas.drawPath(pdf_path, stroke=1, fill=0)
                    drawn = True
        
        # Add more entity types as needed
        
        return drawn
    except AttributeError as e:
        # print(f"DEBUG: Attribute error processing entity {entity.dxftype()}: {e}")
        return False
    except Exception as e:
        # print(f"DEBUG: Error drawing entity {entity.dxftype()}: {e}")
        return False


def create_tiled_a4_pdf_from_dxf(dxf_filepath, pdf_filepath):
    """Creates a potentially multi-page A4 Landscape PDF tiled at 1:1 scale."""
    if not os.path.exists(dxf_filepath):
        print(f"FATAL: DXF file not found at '{dxf_filepath}'")
        return

    print(f"--- Reading DXF: {dxf_filepath} ---")
    try:
        doc = ezdxf.readfile(dxf_filepath)
        msp = doc.modelspace()
        print("DEBUG: DXF read successfully.")
    except ezdxf.DXFStructureError as e:
        print(f"FATAL: Invalid or corrupt DXF file structure: {e}")
        return
    except Exception as e:
        print(f"FATAL: Error reading DXF file: {e}")
        return

    # --- Calculate DXF Extents ---
    print("--- Calculating Extents ---")
    overall_bbox = get_modelspace_extents(doc)
    if overall_bbox is None or not overall_bbox.has_data:
        print("FATAL: Could not determine DXF extents.")
        return

    dxf_width_mm = overall_bbox.size.x
    dxf_height_mm = overall_bbox.size.y
    print(f"DEBUG: DXF Extents Min: ({overall_bbox.extmin.x:.2f}, {overall_bbox.extmin.y:.2f}) mm")
    print(f"DEBUG: DXF Extents Max: ({overall_bbox.extmax.x:.2f}, {overall_bbox.extmax.y:.2f}) mm")
    print(f"DEBUG: DXF content size (W x H): {dxf_width_mm:.2f} mm x {dxf_height_mm:.2f} mm")

    # --- Calculate Page Layout ---
    page_width_mm = PAGE_WIDTH_PT / POINTS_PER_MM
    page_height_mm = PAGE_HEIGHT_PT / POINTS_PER_MM
    print(f"DEBUG: A4 Landscape page size (W x H): {page_width_mm:.2f} mm x {page_height_mm:.2f} mm")

    # Add checks for zero dimensions
    if page_width_mm <= 0 or page_height_mm <= 0:
        print("FATAL: Page dimensions are zero or negative.")
        return
    if dxf_width_mm <= 0 or dxf_height_mm <= 0:
        print("WARNING: DXF content width or height is zero or negative.")

    num_pages_x = math.ceil(dxf_width_mm / page_width_mm) if dxf_width_mm > 0 else 1
    num_pages_y = math.ceil(dxf_height_mm / page_height_mm) if dxf_height_mm > 0 else 1
    total_pages = num_pages_x * num_pages_y

    if total_pages <= 0:
        print("FATAL: No pages calculated. Check DXF extents and page size.")
        return
    print(f"DEBUG: Calculated Pages: {num_pages_x} x {num_pages_y} = {total_pages}")

    # --- Create PDF ---
    print(f"--- Creating PDF: {pdf_filepath} ---")
    c = canvas.Canvas(pdf_filepath, pagesize=(PAGE_WIDTH_PT, PAGE_HEIGHT_PT))
    scale = POINTS_PER_MM
    print(f"DEBUG: Scale factor (points/mm): {scale:.3f}")

    # --- Iterate through pages ---
    page_num = 0
    for page_y in range(num_pages_y):
        for page_x in range(num_pages_x):
            page_num += 1
            print(f"\n--- Drawing Page {page_num}/{total_pages} (Tile Col={page_x+1}, Row={page_y+1}) ---")

            # --- Calculate Offset ---
            tile_origin_x_mm = overall_bbox.extmin.x + page_x * page_width_mm
            tile_origin_y_mm = overall_bbox.extmin.y + page_y * page_height_mm
            final_offset_x_pt = -tile_origin_x_mm * scale
            final_offset_y_pt = -tile_origin_y_mm * scale
            print(f"  DEBUG: Tile Origin (DXF mm): ({tile_origin_x_mm:.2f}, {tile_origin_y_mm:.2f})")
            print(f"  DEBUG: Final Offset (PDF pt): ({final_offset_x_pt:.2f}, {final_offset_y_pt:.2f})")

            # --- Set up Page State ---
            c.saveState()
            print("  DEBUG: Applying page state")

            c.setLineWidth(DEFAULT_LINE_WIDTH)
            c.setStrokeColorRGB(0, 0, 0)

            # Optional: Add page/tile identifier
            c.setFont("Helvetica", 8)
            c.setFillColorRGB(0.5, 0.5, 0.5)
            c.drawString(5 * mm, 5 * mm, f"Page {page_num}/{total_pages} (X{page_x+1}, Y{page_y+1})")
            c.drawString(5 * mm, PAGE_HEIGHT_PT - 5 * mm, f"File: {os.path.basename(dxf_filepath)} @ 1:1 Scale")
            c.setFillColorRGB(0, 0, 0)

            # --- Draw Entities Directly ---
            print("  DEBUG: Iterating through modelspace entities...")
            processed_count = 0
            drawn_entities = 0
            entity_types = {}  # Dictionary to count entity types

            # --- First Pass: Identify Entity Types ---
            print("  DEBUG: Identifying entity types...")
            for entity in msp:
                entity_type = entity.dxftype()
                entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
            print(f"  DEBUG: Found Entity Type Counts: {entity_types}")

            # --- Second Pass: Attempt to Draw Directly ---
            print("  DEBUG: Attempting to draw entities directly...")
            for entity_index, entity in enumerate(msp):
                processed_count += 1
                try:
                    if draw_entity_on_pdf(entity, c, final_offset_x_pt, final_offset_y_pt, scale):
                        drawn_entities += 1
                except Exception as e:
                    # print(f"    DEBUG: Error processing entity {entity.dxftype()}: {e}")
                    pass

            print(f"  DEBUG: Processed {processed_count} top-level entities.")
            print(f"  DEBUG: Successfully drew {drawn_entities} entities.")
            if drawn_entities == 0 and processed_count > 0:
                print("  WARNING: No entities were drawn successfully!")

            # --- Finish Page ---
            print("  DEBUG: Restoring page state.")
            c.restoreState()
            if page_num < total_pages:
                print("  DEBUG: Showing page.")
                c.showPage()
            else:
                print("  DEBUG: Last page, preparing to save.")

    # --- Save PDF ---
    print("--- Saving PDF ---")
    c.save()
    print("DEBUG: PDF save command issued.")


# --- Main Execution ---
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python a4.py <input_dxf_file> <output_pdf_file>")
        sys.exit(1)

    input_dxf = sys.argv[1]
    output_pdf = sys.argv[2]

    create_tiled_a4_pdf_from_dxf(input_dxf, output_pdf)
