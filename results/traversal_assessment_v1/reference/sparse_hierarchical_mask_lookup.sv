`timescale 1ns/1ps

// Determine whether one LR coordinate belongs to the receptive-field closure
// of any selected macro-tile. The original implementation compared every
// coordinate against all 60 tiles. This implementation only inspects the
// coordinate's own tile and its eight immediate neighbors because the largest
// supported radius is smaller than either macro-tile dimension. Columns use a
// power-of-two tile width, while rows use a short constant-boundary decoder.
// Three local row masks then replace both division and a 60-rectangle search.
module sparse_hierarchical_mask_lookup #(
    parameter integer IMAGE_WIDTH = 640,
    parameter integer IMAGE_HEIGHT = 360,
    parameter integer MASK_TILE_WIDTH = 64,
    parameter integer MASK_TILE_HEIGHT = 60,
    parameter integer RADIUS = 0,
    parameter integer COLUMN_BITS =
        (IMAGE_WIDTH <= 1) ? 1 : $clog2(IMAGE_WIDTH),
    parameter integer ROW_BITS =
        (IMAGE_HEIGHT <= 1) ? 1 : $clog2(IMAGE_HEIGHT)
) (
    input  logic [63:0]                    selected_tile_mask,
    input  logic [ROW_BITS-1:0]            row,
    input  logic [COLUMN_BITS-1:0]         column,
    output logic                           selected
);
    localparam integer MASK_TILE_COLUMNS =
        (IMAGE_WIDTH + MASK_TILE_WIDTH - 1) / MASK_TILE_WIDTH;
    localparam integer MASK_TILE_ROWS =
        (IMAGE_HEIGHT + MASK_TILE_HEIGHT - 1) / MASK_TILE_HEIGHT;
    localparam integer MASK_TILE_COLUMN_BITS =
        (MASK_TILE_COLUMNS <= 1) ? 1 : $clog2(MASK_TILE_COLUMNS);
    localparam integer MASK_TILE_ROW_BITS =
        (MASK_TILE_ROWS <= 1) ? 1 : $clog2(MASK_TILE_ROWS);
    localparam integer TILE_COLUMN_OFFSET_BITS = $clog2(MASK_TILE_WIDTH);

    integer row_value;
    integer decoded_row;
    integer row_boundary;
    integer row_offset_value;
    logic [MASK_TILE_ROW_BITS-1:0] tile_row;
    logic [MASK_TILE_COLUMN_BITS-1:0] tile_column;
    logic [TILE_COLUMN_OFFSET_BITS-1:0] column_offset;
    logic [MASK_TILE_COLUMNS-1:0] previous_tile_row_mask;
    logic [MASK_TILE_COLUMNS-1:0] current_tile_row_mask;
    logic [MASK_TILE_COLUMNS-1:0] next_tile_row_mask;
    logic near_previous_row;
    logic near_next_row;
    logic near_previous_column;
    logic near_next_column;

    // Select the three tile-mask rows surrounding the queried coordinate. This
    // is a six-way mux of ten-bit rows rather than repeated 64-way bit selects.
    // Missing rows are represented as zero, which naturally clips the image.
    always @* begin
        row_value = $unsigned(row);
        decoded_row = 0;
        row_offset_value = row_value;
        for (row_boundary = 1; row_boundary < MASK_TILE_ROWS;
             row_boundary = row_boundary + 1) begin
            if (row_value >= row_boundary * MASK_TILE_HEIGHT) begin
                decoded_row = row_boundary;
                row_offset_value = row_value - row_boundary * MASK_TILE_HEIGHT;
            end
        end
        tile_row = decoded_row[MASK_TILE_ROW_BITS-1:0];
        // Constant shift/mask expressions remain valid when a unit test uses
        // an image narrower than one macro-tile. Direct part-selects would
        // otherwise reverse their bounds when COLUMN_BITS is less than six.
        tile_column = $unsigned(column) >> TILE_COLUMN_OFFSET_BITS;
        column_offset = $unsigned(column) & (MASK_TILE_WIDTH - 1);

        previous_tile_row_mask = '0;
        current_tile_row_mask = '0;
        next_tile_row_mask = '0;
        case (decoded_row)
            0: begin
                current_tile_row_mask = selected_tile_mask[0 +: MASK_TILE_COLUMNS];
                if (MASK_TILE_ROWS > 1)
                    next_tile_row_mask =
                        selected_tile_mask[MASK_TILE_COLUMNS +: MASK_TILE_COLUMNS];
            end
            1: begin
                previous_tile_row_mask = selected_tile_mask[0 +: MASK_TILE_COLUMNS];
                current_tile_row_mask =
                    selected_tile_mask[MASK_TILE_COLUMNS +: MASK_TILE_COLUMNS];
                if (MASK_TILE_ROWS > 2)
                    next_tile_row_mask =
                        selected_tile_mask[2*MASK_TILE_COLUMNS +: MASK_TILE_COLUMNS];
            end
            2: begin
                previous_tile_row_mask =
                    selected_tile_mask[MASK_TILE_COLUMNS +: MASK_TILE_COLUMNS];
                current_tile_row_mask =
                    selected_tile_mask[2*MASK_TILE_COLUMNS +: MASK_TILE_COLUMNS];
                if (MASK_TILE_ROWS > 3)
                    next_tile_row_mask =
                        selected_tile_mask[3*MASK_TILE_COLUMNS +: MASK_TILE_COLUMNS];
            end
            3: begin
                previous_tile_row_mask =
                    selected_tile_mask[2*MASK_TILE_COLUMNS +: MASK_TILE_COLUMNS];
                current_tile_row_mask =
                    selected_tile_mask[3*MASK_TILE_COLUMNS +: MASK_TILE_COLUMNS];
                if (MASK_TILE_ROWS > 4)
                    next_tile_row_mask =
                        selected_tile_mask[4*MASK_TILE_COLUMNS +: MASK_TILE_COLUMNS];
            end
            4: begin
                previous_tile_row_mask =
                    selected_tile_mask[3*MASK_TILE_COLUMNS +: MASK_TILE_COLUMNS];
                current_tile_row_mask =
                    selected_tile_mask[4*MASK_TILE_COLUMNS +: MASK_TILE_COLUMNS];
                if (MASK_TILE_ROWS > 5)
                    next_tile_row_mask =
                        selected_tile_mask[5*MASK_TILE_COLUMNS +: MASK_TILE_COLUMNS];
            end
            default: begin
                previous_tile_row_mask =
                    selected_tile_mask[4*MASK_TILE_COLUMNS +: MASK_TILE_COLUMNS];
                current_tile_row_mask =
                    selected_tile_mask[5*MASK_TILE_COLUMNS +: MASK_TILE_COLUMNS];
            end
        endcase

        near_previous_row = row_offset_value < RADIUS;
        near_next_row = row_offset_value >= MASK_TILE_HEIGHT - RADIUS;
        near_previous_column = column_offset < RADIUS;
        near_next_column = column_offset >= MASK_TILE_WIDTH - RADIUS;

        // The current tile always participates. Neighbor bits participate only
        // within the exact radius of the matching horizontal/vertical border;
        // diagonal tiles require both border conditions.
        selected = current_tile_row_mask[tile_column];
        if (tile_column > 0 && near_previous_column)
            selected = selected | current_tile_row_mask[tile_column - 1'b1];
        if (tile_column + 1 < MASK_TILE_COLUMNS && near_next_column)
            selected = selected | current_tile_row_mask[tile_column + 1'b1];
        if (near_previous_row) begin
            selected = selected | previous_tile_row_mask[tile_column];
            if (tile_column > 0 && near_previous_column)
                selected = selected |
                    previous_tile_row_mask[tile_column - 1'b1];
            if (tile_column + 1 < MASK_TILE_COLUMNS && near_next_column)
                selected = selected |
                    previous_tile_row_mask[tile_column + 1'b1];
        end
        if (near_next_row) begin
            selected = selected | next_tile_row_mask[tile_column];
            if (tile_column > 0 && near_previous_column)
                selected = selected | next_tile_row_mask[tile_column - 1'b1];
            if (tile_column + 1 < MASK_TILE_COLUMNS && near_next_column)
                selected = selected | next_tile_row_mask[tile_column + 1'b1];
        end
    end

    initial begin
        if (RADIUS < 0 || RADIUS >= MASK_TILE_WIDTH ||
            RADIUS >= MASK_TILE_HEIGHT)
            $error("RADIUS must be nonnegative and smaller than each mask tile");
        if (MASK_TILE_COLUMNS * MASK_TILE_ROWS > 64)
            $error("selected_tile_mask supports at most 64 macro-tiles");
        if ((1 << TILE_COLUMN_OFFSET_BITS) != MASK_TILE_WIDTH)
            $error("MASK_TILE_WIDTH must be a power of two");
        if (MASK_TILE_ROWS > 6)
            $error("bounded row decoder currently supports at most six tile rows");
    end
endmodule
