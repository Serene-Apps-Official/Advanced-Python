# Multiprocessing example
import multiprocessing
import time

def square_numbers():
    for i in range(5):
        print(i * i)
        time.sleep(1)

if __name__ == "__main__":
    processes = []
    for _ in range(5):
        p = multiprocessing.Process(target=square_numbers)
        processes.append(p)
        p.start()
    
    for p in processes:
        p.join()