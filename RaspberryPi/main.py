import time

from inputs.mouse_input import MouseInput


def main():
    mouse = MouseInput()
    mouse.start()

    try:
        while True:
            if mouse.is_moved():
                x, y = mouse.get_absolute_position()
                print(f"x={x} y={y}")
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        mouse.stop()


if __name__ == "__main__":
    main()