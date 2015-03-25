 /* 
 *  A simple TCP proxy
 *  by Martin Broadhurst (www.martinbroadhurst.com)
 */

#include <stdio.h>
#include <string.h> /* memset() */
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <netdb.h>
#include <signal.h>
#include <pthread.h>
#include <stdlib.h>

#define PORT     "6379" /* Port to listen on */
#define BACKLOG  10      /* Passed to listen() */
#define BUF_SIZE 4096    /* Buffer for  transfers */

unsigned int transfer(int from, int to)
{
    //printf("TRANSFER FROM %d to %d\n", from, to);
    char buf[BUF_SIZE];
    unsigned int disconnected = 0;
    size_t bytes_read, bytes_written;
    bytes_read = read(from, buf, BUF_SIZE);
    if (bytes_read == 0) {
        disconnected = 1;
    }
    else {
        bytes_written = write(to, buf, bytes_read);
        if (bytes_written == -1) {
            disconnected = 1;
        }
    }
    return disconnected;
}

struct args{

int client;
const char *host;
const char *port;

};


//void handle(int client, const char *host, const char *port)
void handle(struct args *args)
{
    struct addrinfo hints, *res;
    int server = -1;
    unsigned int disconnected = 0;
    fd_set set;
    unsigned int max_sock;

    /* Get the address info */
    memset(&hints, 0, sizeof hints);
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo(args->host, args->port, &hints, &res) != 0) {
        perror("getaddrinfo");
        close(args->client);
        return;
    }

    /* Create the socket */
    server = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (server == -1) {
        perror("socket");
        close(args->client);
        return;
    }

    /* Connect to the host */
    //printf("Now trying to connect to redis...\n");
    if (connect(server, res->ai_addr, res->ai_addrlen) == -1) {
        perror("connect");
        close(args->client);
        return;
    }

    if (args->client > server) {
        max_sock = args->client;
    }
    else {
        max_sock = server;
    }

    /* Main transfer loop */
    while (!disconnected) {
        //printf("Inside transfer loop (%d, %d)!!\n",args->client, server);
        FD_ZERO(&set);
        FD_SET(args->client, &set);
        FD_SET(server, &set);
        if (select(max_sock + 1, &set, NULL, NULL, NULL) == -1) {
            perror("select");
            break;
        }
        //printf("SELECTED!!\n");
        if (FD_ISSET(args->client, &set)) {
            //printf("transfering from client %d  to server %d\n", args->client, server);
            disconnected = transfer(args->client, server);
            //printf("transfer complete from client %d  to server %d\n", args->client, server);
        }
        if (FD_ISSET(server, &set)) {
            //printf("transfering from server %d to client %d\n", server, args->client);
            disconnected = transfer(server, args->client);
            //printf("transfer complete from server %d to client %d\n", server, args->client);
        }
    }
    //printf("CLOSED!\n");
    close(server);
    close(args->client);
    free(args);
}

int main(int argc, char **argv)
{
    int sock;
    struct addrinfo hints, *res;
    int reuseaddr = 1; /* True */
    const char * host, * port;

   // /* Get the server host and port from the command line */
   // if (argc < 3) {
   //     f//printf(stderr, "Usage: tcpproxy host port\n");
   //     return 1;
   // }
    host = "localhost";//argv[1];
    port = "16379";//argv[2];

    /* Get the address info */
    memset(&hints, 0, sizeof hints);
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo(NULL, PORT, &hints, &res) != 0) {
        perror("getaddrinfo");
        return 1;
    }

    /* Create the socket */
    sock = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (sock == -1) {
        perror("socket");
        return 1;
    }

    /* Enable the socket to reuse the address */
    if (setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &reuseaddr, sizeof(int)) == -1) {
        perror("setsockopt");
        return 1;
    }

    /* Bind to the address */
    if (bind(sock, res->ai_addr, res->ai_addrlen) == -1) {
        perror("bind");
        return 1;
    }

    /* Listen */
    if (listen(sock, BACKLOG) == -1) {
        perror("listen");
        return 1;
    }

    freeaddrinfo(res);

    /* Ignore broken pipe signal */
    signal(SIGPIPE, SIG_IGN);
    //printf("ENTERING LOOP\n");
 
    pthread_t threadpool[500]; // I added this... Excessive.  Lazy. 
    int count = 0;
    /* Main loop */
    while (1) {
        socklen_t size = sizeof(struct sockaddr_in);
        struct sockaddr_in their_addr;
        //printf("CALLING ACCEPT\n");
        int newsock = accept(sock, (struct sockaddr*)&their_addr, &size);

        if (newsock == -1) {
            perror("accept");
        }
        else {
            //printf("Got a connection from %s on port %d newsock: %d\n",
                    //inet_ntoa(their_addr.sin_addr), htons(their_addr.sin_port), newsock);
            //I added this too.
            struct args *a = malloc(sizeof(struct args));  // freed inside handle function
            a->client = newsock; 
            a->host = host; 
            a->port = port;
            pthread_create(&threadpool[count], NULL, (void *) &handle, (void*)a);  
            count++;
            //handle(newsock, host, port);
        }
    }
    //TODO um, join the threads and do something less lazy.
    close(sock);

    return 0;
}


